import subprocess
from pathlib import Path
from typing import Callable, List, Optional


class BuildError(Exception):
    """Raised when docker build fails."""
    def __init__(self, message: str, log_tail: Optional[str] = None):
        super().__init__(message)
        self.log_tail = log_tail


def build_image(
    build_dir: Path,
    image_tag: str,
    timeout_seconds: int = 600,
    log_callback: Optional[Callable[[str], None]] = None,
) -> List[str]:
    """
    Executes 'docker build -t <image_tag> .' in build_dir.
    Streams output lines to log_callback and returns all collected logs.
    """
    cmd = ["docker", "build", "-t", image_tag, "."]
    collected_logs: List[str] = []

    def handle_line(line: str):
        cleaned = line.rstrip()
        collected_logs.append(cleaned)
        if log_callback:
            log_callback(cleaned)

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(build_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        for line in iter(process.stdout.readline, ""):
            handle_line(line)

        process.stdout.close()
        return_code = process.wait(timeout=timeout_seconds)

        if return_code != 0:
            tail = "\n".join(collected_logs[-25:]) if collected_logs else "No logs"
            raise BuildError(
                f"Docker build failed with exit code {return_code}",
                log_tail=tail,
            )

        return collected_logs

    except subprocess.TimeoutExpired:
        process.kill()
        raise BuildError(f"Docker build timed out after {timeout_seconds} seconds")
    except BuildError:
        raise
    except Exception as e:
        raise BuildError(f"Unexpected error during docker build: {str(e)}")
