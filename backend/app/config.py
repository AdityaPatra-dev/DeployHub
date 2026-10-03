from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "DeployHub"
    DEBUG: bool = False

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    WORKSPACES_DIR: Path = BASE_DIR / ".deployhub-workspaces"

    # Engine Defaults
    HOST_BIND_IP: str = "127.0.0.1"
    PORT_RANGE_START: int = 32000
    PORT_RANGE_END: int = 40000
    DEFAULT_BUILD_TIMEOUT: int = 600
    DEFAULT_HEALTH_TIMEOUT: int = 120
    DEFAULT_CLONE_TIMEOUT: int = 60

    # Resource Limits for Docker containers
    CONTAINER_MEMORY_LIMIT: str = "512m"
    CONTAINER_CPUS_LIMIT: float = 0.5
    CONTAINER_PIDS_LIMIT: int = 256

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
