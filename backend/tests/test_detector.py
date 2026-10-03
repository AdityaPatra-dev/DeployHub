import pytest
from pathlib import Path
from app.engine.detector import detect_project, extract_exposed_port, ProjectDetectionError
from app.engine.models import ProjectType


def test_detect_python_requirements(tmp_path):
    (tmp_path / "requirements.txt").write_text("fastapi==0.110.0\n")
    res = detect_project(tmp_path)
    assert res.project_type == ProjectType.PYTHON
    assert res.detected_file == "requirements.txt"
    assert res.default_port == 8000
    assert not res.has_dockerfile


def test_detect_python_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    res = detect_project(tmp_path)
    assert res.project_type == ProjectType.PYTHON
    assert res.detected_file == "pyproject.toml"
    assert res.default_port == 8000


def test_detect_nodejs(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "test"}')
    res = detect_project(tmp_path)
    assert res.project_type == ProjectType.NODEJS
    assert res.detected_file == "package.json"
    assert res.default_port == 3000


def test_detect_dockerfile(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM alpine\nEXPOSE 9090\n")
    res = detect_project(tmp_path)
    assert res.project_type == ProjectType.DOCKERFILE
    assert res.default_port == 9090
    assert res.has_dockerfile


def test_detect_ambiguous_fails(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "test"}')
    (tmp_path / "requirements.txt").write_text("flask")
    with pytest.raises(ProjectDetectionError, match="Ambiguous project type"):
        detect_project(tmp_path)


def test_detect_unsupported_fails(tmp_path):
    with pytest.raises(ProjectDetectionError, match="Unsupported project type"):
        detect_project(tmp_path)


def test_extract_exposed_port(tmp_path):
    df = tmp_path / "Dockerfile"
    df.write_text("FROM python:3.12-slim\nEXPOSE 8080\nCMD ['python']")
    assert extract_exposed_port(df) == 8080
