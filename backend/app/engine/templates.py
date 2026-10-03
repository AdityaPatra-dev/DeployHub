from pathlib import Path
from app.engine.models import ProjectDetectionResult, ProjectType

DOCKERIGNORE_CONTENT = """# DeployHub auto-generated .dockerignore
.git
.gitignore
node_modules
npm-debug.log
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
.env
.env.*
.pytest_cache/
.coverage
htmlcov/
.DS_Store
"""

PYTHON_TEMPLATE_REQUIREMENTS = """FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for build layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Run as non-root user (numeric UID 10001 for Kubernetes compliance)
RUN useradd --uid 10001 --no-create-home appuser
USER 10001

ENV PORT={port}
EXPOSE {port}

CMD ["python", "main.py"]
"""

PYTHON_TEMPLATE_PYPROJECT = """FROM python:3.12-slim

WORKDIR /app

# Copy project definition and install
COPY pyproject.toml .
COPY . .
RUN pip install --no-cache-dir .

# Run as non-root user (numeric UID 10001 for Kubernetes compliance)
RUN useradd --uid 10001 --no-create-home appuser
USER 10001

ENV PORT={port}
EXPOSE {port}

CMD ["python", "main.py"]
"""

NODE_TEMPLATE = """FROM node:22-slim

WORKDIR /app

# Install production dependencies first
COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci --omit=dev; else npm install --omit=dev; fi

# Copy application source
COPY . .

# Ensure app files are readable by non-root user
USER 10001

ENV PORT={port}
EXPOSE {port}

CMD ["npm", "start"]
"""


def generate_dockerfile(detection: ProjectDetectionResult, target_dir: Path, port: int) -> Path:
    """
    Generates a secure, optimized Dockerfile for the project if one doesn't exist.
    Also ensures a .dockerignore is written.
    """
    dockerfile_path = target_dir / "Dockerfile"
    dockerignore_path = target_dir / ".dockerignore"

    # Always ensure a .dockerignore exists to protect credentials and speed up build
    if not dockerignore_path.exists():
        dockerignore_path.write_text(DOCKERIGNORE_CONTENT, encoding="utf-8")

    if detection.has_dockerfile and dockerfile_path.exists():
        return dockerfile_path

    if detection.project_type == ProjectType.PYTHON:
        if detection.detected_file == "requirements.txt":
            content = PYTHON_TEMPLATE_REQUIREMENTS.format(port=port)
        else:
            content = PYTHON_TEMPLATE_PYPROJECT.format(port=port)
    elif detection.project_type == ProjectType.NODEJS:
        content = NODE_TEMPLATE.format(port=port)
    else:
        raise ValueError(f"Cannot generate Dockerfile for project type: {detection.project_type}")

    dockerfile_path.write_text(content, encoding="utf-8")
    return dockerfile_path
