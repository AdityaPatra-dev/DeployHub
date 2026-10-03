from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class DeploymentStatus(str, Enum):
    QUEUED = "QUEUED"
    CLONING = "CLONING"
    BUILDING = "BUILDING"
    PUSHING = "PUSHING"
    DEPLOYING = "DEPLOYING"
    HEALTH_CHECK = "HEALTH_CHECK"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class ProjectType(str, Enum):
    DOCKERFILE = "dockerfile"
    PYTHON = "python"
    NODEJS = "nodejs"
    UNKNOWN = "unknown"


class ProjectDetectionResult(BaseModel):
    project_type: ProjectType
    detected_file: str
    default_port: int
    start_command: Optional[str] = None
    has_dockerfile: bool = False


class DeploymentConfig(BaseModel):
    repository: str = Field(..., description="Repository URL or local path")
    branch: str = Field(default="main", description="Git branch to clone")
    port: Optional[int] = Field(default=None, description="App port (auto-detected if None)")
    project_name: Optional[str] = Field(default=None, description="Project name")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    health_path: str = Field(default="/health", description="HTTP health check path")
    build_timeout_seconds: int = Field(default=600, description="Max build time in seconds")
    health_timeout_seconds: int = Field(default=120, description="Max health check time in seconds")


class DeploymentLogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stage: DeploymentStatus
    message: str


class DeploymentResult(BaseModel):
    deployment_id: str
    status: DeploymentStatus
    project_name: str
    commit_sha: Optional[str] = None
    image: Optional[str] = None
    container_id: Optional[str] = None
    container_name: Optional[str] = None
    host_port: Optional[int] = None
    container_port: Optional[int] = None
    url: Optional[str] = None
    failure_stage: Optional[str] = None
    error_message: Optional[str] = None
    logs: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
