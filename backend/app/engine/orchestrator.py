import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from app.config import settings
from app.engine.builder import BuildError, build_image
from app.engine.cloner import CloningError, clone_repository
from app.engine.detector import ProjectDetectionError, detect_project
from app.engine.health import HealthCheckError, wait_for_healthy
from app.engine.models import (
    DeploymentConfig,
    DeploymentResult,
    DeploymentStatus,
)
from app.engine.runner import RunnerError, find_free_port, run_container
from app.engine.templates import generate_dockerfile


class DeploymentOrchestrator:
    """
    Coordinates the complete lifecycle from repository to running container.
    Manages deterministic state machine transitions:
    QUEUED -> CLONING -> BUILDING -> DEPLOYING -> HEALTH_CHECK -> RUNNING (or FAILED)
    """

    def __init__(self, workspaces_dir: Optional[Path] = None):
        self.workspaces_dir = workspaces_dir or settings.WORKSPACES_DIR
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)

    def deploy(
        self,
        config: DeploymentConfig,
        on_status_change: Optional[Callable[[DeploymentStatus, str], None]] = None,
    ) -> DeploymentResult:
        deployment_id = uuid.uuid4().hex[:8]
        project_name = config.project_name or self._infer_project_name(config.repository)
        workspace = self.workspaces_dir / f"{project_name}_{deployment_id}"

        result = DeploymentResult(
            deployment_id=deployment_id,
            status=DeploymentStatus.QUEUED,
            project_name=project_name,
            logs=[],
        )

        def log(stage: DeploymentStatus, message: str):
            line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] [{stage.value}] {message}"
            result.logs.append(line)
            if on_status_change:
                on_status_change(stage, line)

        log(DeploymentStatus.QUEUED, f"Deployment {deployment_id} queued for {project_name}")

        try:
            # 1. CLONING
            result.status = DeploymentStatus.CLONING
            log(DeploymentStatus.CLONING, f"Fetching repository: {config.repository} (branch: {config.branch})")
            commit_sha, clone_msg = clone_repository(
                repository=config.repository,
                branch=config.branch,
                target_dir=workspace,
                timeout_seconds=settings.DEFAULT_CLONE_TIMEOUT,
            )
            result.commit_sha = commit_sha
            log(DeploymentStatus.CLONING, clone_msg)

            # 2. DETECT RUNTIME & GENERATE DOCKERFILE
            log(DeploymentStatus.BUILDING, "Inspecting repository and detecting application runtime...")
            detection = detect_project(workspace)
            target_port = config.port or detection.default_port
            result.container_port = target_port
            log(
                DeploymentStatus.BUILDING,
                f"Detected runtime: {detection.project_type.value} via '{detection.detected_file}' (Port: {target_port})",
            )

            # Generate Dockerfile and .dockerignore if necessary
            generate_dockerfile(detection, workspace, port=target_port)

            # 3. BUILDING IMAGE
            result.status = DeploymentStatus.BUILDING
            image_tag = f"deployhub/{project_name}:{commit_sha}"
            result.image = image_tag
            log(DeploymentStatus.BUILDING, f"Building Docker image: {image_tag}")

            build_logs = build_image(
                build_dir=workspace,
                image_tag=image_tag,
                timeout_seconds=config.build_timeout_seconds,
                log_callback=lambda l: result.logs.append(f"  {l}"),
            )
            log(DeploymentStatus.BUILDING, f"Successfully built image: {image_tag}")

            # 4. DEPLOYING CONTAINER
            result.status = DeploymentStatus.DEPLOYING
            host_port = find_free_port(
                host=settings.HOST_BIND_IP,
                start_port=settings.PORT_RANGE_START,
                end_port=settings.PORT_RANGE_END,
            )
            container_name = f"dh-{project_name}-{deployment_id}"
            result.container_name = container_name
            result.host_port = host_port

            log(
                DeploymentStatus.DEPLOYING,
                f"Starting container '{container_name}' (Port mapping: {host_port}->{target_port})...",
            )
            container_id = run_container(
                image_tag=image_tag,
                container_name=container_name,
                container_port=target_port,
                host_port=host_port,
                env_vars=config.env_vars,
                memory_limit=settings.CONTAINER_MEMORY_LIMIT,
                cpus_limit=settings.CONTAINER_CPUS_LIMIT,
                pids_limit=settings.CONTAINER_PIDS_LIMIT,
            )
            result.container_id = container_id[:12]
            log(DeploymentStatus.DEPLOYING, f"Container started: {result.container_id}")

            # 5. HEALTH CHECK
            result.status = DeploymentStatus.HEALTH_CHECK
            log(
                DeploymentStatus.HEALTH_CHECK,
                f"Awaiting health check on http://{settings.HOST_BIND_IP}:{host_port}{config.health_path}...",
            )
            wait_for_healthy(
                host=settings.HOST_BIND_IP,
                port=host_port,
                health_path=config.health_path,
                container_name_or_id=container_name,
                timeout_seconds=config.health_timeout_seconds,
            )
            log(DeploymentStatus.HEALTH_CHECK, "Health check passed successfully!")

            # 6. RUNNING
            result.status = DeploymentStatus.RUNNING
            result.url = f"http://{settings.HOST_BIND_IP}:{host_port}"
            result.finished_at = datetime.now(timezone.utc)
            log(DeploymentStatus.RUNNING, f"Deployment completed successfully. Live URL: {result.url}")

            # Clean workspace files to save disk
            shutil.rmtree(workspace, ignore_errors=True)
            return result

        except CloningError as e:
            return self._fail(result, DeploymentStatus.CLONING, str(e), log)
        except ProjectDetectionError as e:
            return self._fail(result, DeploymentStatus.BUILDING, str(e), log)
        except BuildError as e:
            err = f"{str(e)}\n\nLast Build Output:\n{e.log_tail}" if e.log_tail else str(e)
            return self._fail(result, DeploymentStatus.BUILDING, err, log)
        except RunnerError as e:
            return self._fail(result, DeploymentStatus.DEPLOYING, str(e), log)
        except HealthCheckError as e:
            err = f"{str(e)}\n\nContainer Logs:\n{e.container_logs}" if e.container_logs else str(e)
            return self._fail(result, DeploymentStatus.HEALTH_CHECK, err, log)
        except Exception as e:
            return self._fail(result, result.status, f"Unexpected failure: {str(e)}", log)

    def _fail(
        self,
        result: DeploymentResult,
        stage: DeploymentStatus,
        error_msg: str,
        log_fn: Callable[[DeploymentStatus, str], None],
    ) -> DeploymentResult:
        result.status = DeploymentStatus.FAILED
        result.failure_stage = stage.value
        result.error_message = error_msg
        result.finished_at = datetime.now(timezone.utc)
        log_fn(DeploymentStatus.FAILED, f"Failed at {stage.value}: {error_msg}")
        return result

    def _infer_project_name(self, repository: str) -> str:
        clean = repository.rstrip("/")
        if clean.endswith(".git"):
            clean = clean[:-4]
        name = Path(clean).name or "app"
        return "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in name).lower()
