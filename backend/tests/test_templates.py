from pathlib import Path
from app.engine.models import ProjectDetectionResult, ProjectType
from app.engine.templates import generate_dockerfile


def test_generate_python_dockerfile(tmp_path):
    detection = ProjectDetectionResult(
        project_type=ProjectType.PYTHON,
        detected_file="requirements.txt",
        default_port=8000,
    )
    df_path = generate_dockerfile(detection, tmp_path, port=8000)
    assert df_path.exists()
    content = df_path.read_text()
    assert "FROM python:3.12-slim" in content
    assert "USER 10001" in content
    assert "EXPOSE 8000" in content
    assert (tmp_path / ".dockerignore").exists()


def test_generate_nodejs_dockerfile(tmp_path):
    detection = ProjectDetectionResult(
        project_type=ProjectType.NODEJS,
        detected_file="package.json",
        default_port=3000,
    )
    df_path = generate_dockerfile(detection, tmp_path, port=3000)
    assert df_path.exists()
    content = df_path.read_text()
    assert "FROM node:22-slim" in content
    assert "USER 10001" in content
    assert "EXPOSE 3000" in content
    assert (tmp_path / ".dockerignore").exists()
