import subprocess
import time
from typing import Optional, Tuple
from app.config import settings


class RegistryError(Exception):
    """Raised when container registry operations fail."""
    pass


class ContainerRegistryService:
    """
    Manages container image tagging, registry authentication, and image pushing
    to OCI-compliant registries (GitHub Container Registry - GHCR, Docker Hub, AWS ECR).
    """

    def __init__(
        self,
        registry_url: Optional[str] = None,
        username: Optional[str] = None,
        token: Optional[str] = None,
    ):
        self.registry_url = (registry_url or getattr(settings, "REGISTRY_URL", "ghcr.io")).rstrip("/")
        self.username = username or getattr(settings, "REGISTRY_USERNAME", "")
        self.token = token or getattr(settings, "REGISTRY_TOKEN", "")
        self.is_configured = bool(self.registry_url and self.username and self.token)

    def format_image_tag(self, project_name: str, commit_sha: str) -> str:
        """
        Generates an immutable image tag: <registry>/<username_or_org>/<project_name>:<commit_sha>
        If no registry is configured, returns local tag: deployhub/<project_name>:<commit_sha>
        """
        clean_project = project_name.lower().replace("_", "-")
        clean_sha = commit_sha.strip()[:7] if commit_sha else "latest"

        if self.is_configured and self.username:
            return f"{self.registry_url}/{self.username.lower()}/{clean_project}:{clean_sha}"
        return f"deployhub/{clean_project}:{clean_sha}"

    def login(self) -> Tuple[bool, str]:
        """Authenticates with the container registry using docker login."""
        if not self.is_configured:
            return False, "Registry credentials not configured. Skipping remote login."

        try:
            proc = subprocess.run(
                [
                    "docker",
                    "login",
                    self.registry_url,
                    "-u",
                    self.username,
                    "--password-stdin",
                ],
                input=self.token,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0:
                return True, f"Successfully logged into {self.registry_url} as {self.username}"
            else:
                error_msg = proc.stderr.strip() or proc.stdout.strip()
                return False, f"Registry login failed: {error_msg}"
        except subprocess.TimeoutExpired:
            return False, f"Registry login timed out after 30s"
        except Exception as e:
            return False, f"Registry login error: {str(e)}"

    def push_image(
        self,
        image_tag: str,
        timeout_seconds: int = 300,
        max_retries: int = 2,
    ) -> Tuple[bool, str]:
        """
        Pushes a tagged container image to the registry with retry logic.
        In local development (credentials unset), marks push as simulated and logs clearly.
        """
        if not self.is_configured:
            return True, f"Registry not configured: image '{image_tag}' retained in local Docker cache."

        attempt = 0
        last_error = ""

        while attempt <= max_retries:
            attempt += 1
            try:
                proc = subprocess.run(
                    ["docker", "push", image_tag],
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
                if proc.returncode == 0:
                    return True, f"Pushed image '{image_tag}' to registry."
                else:
                    last_error = proc.stderr.strip() or proc.stdout.strip()
            except subprocess.TimeoutExpired:
                last_error = f"Push timed out after {timeout_seconds}s"
            except Exception as e:
                last_error = str(e)

            if attempt <= max_retries:
                time.sleep(2 * attempt)  # exponential backoff

        raise RegistryError(f"Failed to push image '{image_tag}' after {max_retries + 1} attempts: {last_error}")


registry_service = ContainerRegistryService()
