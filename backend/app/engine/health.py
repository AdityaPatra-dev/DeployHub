import time
import requests
from typing import Optional
from app.engine.runner import get_container_logs, is_container_running


class HealthCheckError(Exception):
    """Raised when container health check fails."""
    def __init__(self, message: str, container_logs: Optional[str] = None):
        super().__init__(message)
        self.container_logs = container_logs


def wait_for_healthy(
    host: str,
    port: int,
    health_path: str = "/health",
    container_name_or_id: Optional[str] = None,
    timeout_seconds: int = 120,
    interval_seconds: float = 1.0,
) -> bool:
    """
    Polls the application's HTTP health check endpoint until 2xx is returned,
    or until timeout / early container crash.
    """
    start_time = time.time()
    endpoints = [health_path]
    if health_path != "/":
        endpoints.append("/")

    last_error = ""

    while time.time() - start_time < timeout_seconds:
        # 1. Early abort if the container crashed or exited
        if container_name_or_id and not is_container_running(container_name_or_id):
            logs = get_container_logs(container_name_or_id, tail=50)
            raise HealthCheckError(
                f"Container stopped unexpectedly before becoming healthy: {container_name_or_id}",
                container_logs=logs,
            )

        # 2. Try HTTP check on candidate paths
        for path in endpoints:
            url = f"http://{host}:{port}{path}"
            try:
                resp = requests.get(url, timeout=2)
                if 200 <= resp.status_code < 400:
                    return True
                else:
                    last_error = f"HTTP {resp.status_code} returned by {url}"
            except requests.RequestException as e:
                last_error = str(e)

        time.sleep(interval_seconds)

    # Timed out
    logs = get_container_logs(container_name_or_id, tail=50) if container_name_or_id else None
    raise HealthCheckError(
        f"Health check timed out after {timeout_seconds}s at {host}:{port}. Last error: {last_error}",
        container_logs=logs,
    )
