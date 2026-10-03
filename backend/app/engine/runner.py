import socket
import subprocess
from typing import Dict, List, Optional
from app.config import settings


class RunnerError(Exception):
    """Raised when container deployment fails."""
    pass


def find_free_port(host: str = "127.0.0.1", start_port: int = 32000, end_port: int = 40000) -> int:
    """Finds an unused port on the host machine."""
    for port in range(start_port, end_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue

    # Fallback to OS assigned ephemeral port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def remove_container_if_exists(container_name: str) -> None:
    """Stops and removes any existing container with the given name."""
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
        text=True,
    )


def run_container(
    image_tag: str,
    container_name: str,
    container_port: int,
    host_port: int,
    env_vars: Optional[Dict[str, str]] = None,
    memory_limit: str = "512m",
    cpus_limit: float = 0.5,
    pids_limit: int = 256,
) -> str:
    """
    Runs the container using secure and isolated flags per DeployHub spec:
    - --security-opt no-new-privileges
    - Resource limits (memory, cpu, pids)
    - PORT environment variable
    """
    remove_container_if_exists(container_name)

    cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        container_name,
        "-p",
        f"{settings.HOST_BIND_IP}:{host_port}:{container_port}",
        "-e",
        f"PORT={container_port}",
        "--memory",
        memory_limit,
        f"--cpus={cpus_limit}",
        f"--pids-limit={pids_limit}",
        "--security-opt",
        "no-new-privileges",
    ]

    # Inject custom environment variables
    if env_vars:
        for k, v in env_vars.items():
            cmd.extend(["-e", f"{k}={v}"])

    cmd.append(image_tag)

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        error_msg = proc.stderr.strip() or proc.stdout.strip()
        raise RunnerError(f"Failed to start container '{container_name}': {error_msg}")

    container_id = proc.stdout.strip()
    return container_id


def stop_container(container_name: str) -> bool:
    """Stops and deletes the container."""
    proc = subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, text=True)
    return proc.returncode == 0


def get_container_logs(container_name_or_id: str, tail: int = 100) -> str:
    """Retrieves standard output and error logs from a running or exited container."""
    proc = subprocess.run(
        ["docker", "logs", f"--tail={tail}", container_name_or_id],
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def is_container_running(container_name_or_id: str) -> bool:
    """Checks if container is currently in running status."""
    proc = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", container_name_or_id],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() == "true"
