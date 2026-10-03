import shutil
from pathlib import Path
import pytest
import requests

from app.engine.models import DeploymentConfig, DeploymentStatus
from app.engine.orchestrator import DeploymentOrchestrator
from app.engine.runner import stop_container

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"


@pytest.fixture
def orchestrator(tmp_path):
    return DeploymentOrchestrator(workspaces_dir=tmp_path / "workspaces")


def test_deploy_python_sample_app(orchestrator):
    python_app_path = str(EXAMPLES_DIR / "python-app")
    config = DeploymentConfig(
        repository=python_app_path,
        project_name="test-python-app",
        port=8000,
    )

    result = orchestrator.deploy(config)
    try:
        assert result.status == DeploymentStatus.RUNNING
        assert result.url is not None
        assert result.container_name is not None

        # Verify live application response
        resp = requests.get(f"{result.url}/health", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["app"] == "python-sample-app"
    finally:
        if result.container_name:
            stop_container(result.container_name)


def test_deploy_node_sample_app(orchestrator):
    node_app_path = str(EXAMPLES_DIR / "node-app")
    config = DeploymentConfig(
        repository=node_app_path,
        project_name="test-node-app",
        port=3000,
    )

    result = orchestrator.deploy(config)
    try:
        assert result.status == DeploymentStatus.RUNNING
        assert result.url is not None
        assert result.container_name is not None

        # Verify live application response
        resp = requests.get(f"{result.url}/health", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["app"] == "node-sample-app"
    finally:
        if result.container_name:
            stop_container(result.container_name)


def test_deploy_dockerfile_sample_app(orchestrator):
    dockerfile_app_path = str(EXAMPLES_DIR / "dockerfile-app")
    config = DeploymentConfig(
        repository=dockerfile_app_path,
        project_name="test-dockerfile-app",
    )

    result = orchestrator.deploy(config)
    try:
        assert result.status == DeploymentStatus.RUNNING
        assert result.url is not None
        assert result.container_name is not None

        # Verify live application response
        resp = requests.get(f"{result.url}/health", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["app"] == "dockerfile-sample-app"
    finally:
        if result.container_name:
            stop_container(result.container_name)


def test_deploy_invalid_unsupported_project_fails(orchestrator, tmp_path):
    empty_dir = tmp_path / "empty-project"
    empty_dir.mkdir()

    config = DeploymentConfig(
        repository=str(empty_dir),
        project_name="test-empty-app",
    )

    result = orchestrator.deploy(config)
    assert result.status == DeploymentStatus.FAILED
    assert result.failure_stage == "BUILDING"
    assert "Unsupported project type" in result.error_message
