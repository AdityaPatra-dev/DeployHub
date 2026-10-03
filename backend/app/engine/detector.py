import re
from pathlib import Path
from typing import Optional

from app.engine.models import ProjectDetectionResult, ProjectType


class ProjectDetectionError(Exception):
    """Raised when runtime detection fails."""
    pass


def extract_exposed_port(dockerfile_path: Path) -> Optional[int]:
    """Extract exposed port from a Dockerfile if present."""
    if not dockerfile_path.is_file():
        return None
    try:
        content = dockerfile_path.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"^\s*EXPOSE\s+(\d+)", content, re.MULTILINE | re.IGNORECASE)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return None


def detect_project(repo_dir: Path) -> ProjectDetectionResult:
    """
    Inspects repository root and detects runtime type according to DeployHub spec:
    Precedence: Dockerfile -> package.json -> requirements.txt / pyproject.toml
    """
    if not repo_dir.exists() or not repo_dir.is_dir():
        raise ProjectDetectionError(f"Directory does not exist: {repo_dir}")

    dockerfile = repo_dir / "Dockerfile"
    package_json = repo_dir / "package.json"
    requirements_txt = repo_dir / "requirements.txt"
    pyproject_toml = repo_dir / "pyproject.toml"

    # 1. Dockerfile
    if dockerfile.is_file():
        exposed_port = extract_exposed_port(dockerfile) or 8080
        return ProjectDetectionResult(
            project_type=ProjectType.DOCKERFILE,
            detected_file="Dockerfile",
            default_port=exposed_port,
            start_command=None,
            has_dockerfile=True,
        )

    # Check for ambiguous clash between Node and Python when no Dockerfile exists
    has_node = package_json.is_file()
    has_python = requirements_txt.is_file() or pyproject_toml.is_file()

    if has_node and has_python:
        raise ProjectDetectionError(
            "Ambiguous project type: Found both package.json and Python config files. "
            "Please specify a Dockerfile or configure the build method explicitly."
        )

    # 2. Node.js
    if has_node:
        return ProjectDetectionResult(
            project_type=ProjectType.NODEJS,
            detected_file="package.json",
            default_port=3000,
            start_command="npm start",
            has_dockerfile=False,
        )

    # 3. Python
    if requirements_txt.is_file():
        return ProjectDetectionResult(
            project_type=ProjectType.PYTHON,
            detected_file="requirements.txt",
            default_port=8000,
            start_command="python main.py",
            has_dockerfile=False,
        )

    if pyproject_toml.is_file():
        return ProjectDetectionResult(
            project_type=ProjectType.PYTHON,
            detected_file="pyproject.toml",
            default_port=8000,
            start_command="python main.py",
            has_dockerfile=False,
        )

    raise ProjectDetectionError(
        "Unsupported project type: No Dockerfile, package.json, requirements.txt, "
        "or pyproject.toml found in repository root."
    )
