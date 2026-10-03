import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple


class CloningError(Exception):
    """Raised when repository cloning or checkout fails."""
    pass


def clone_repository(
    repository: str,
    branch: str,
    target_dir: Path,
    timeout_seconds: int = 60
) -> Tuple[str, str]:
    """
    Clones the specified repository (or copies local directory) into target_dir.
    Returns: (commit_sha, log_message)
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    repo_path = Path(repository)

    # Handle local path (for local testing / examples without remote push)
    if repo_path.exists() and repo_path.is_dir():
        # Copy files to target_dir (excluding .git / build caches if desired)
        for item in repo_path.iterdir():
            if item.name in (".git", "__pycache__", "node_modules", ".venv"):
                continue
            dest = target_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

        # Try to obtain commit SHA from the source repo if it's inside git
        commit_sha = "local001"
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                commit_sha = res.stdout.strip()[:7]
        except Exception:
            pass

        return commit_sha, f"Prepared local repository from {repo_path} at SHA {commit_sha}"

    # Remote Git clone
    cmd = [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        branch,
        repository,
        str(target_dir),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        raise CloningError(f"Git clone timed out after {timeout_seconds} seconds for repository: {repository}")
    except Exception as e:
        raise CloningError(f"Failed to execute git clone: {str(e)}")

    if proc.returncode != 0:
        error_msg = proc.stderr.strip() or proc.stdout.strip()
        raise CloningError(f"Git clone failed (exit code {proc.returncode}): {error_msg}")

    # Extract commit SHA
    try:
        sha_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if sha_proc.returncode == 0 and sha_proc.stdout.strip():
            commit_sha = sha_proc.stdout.strip()[:7]
        else:
            commit_sha = "unknown"
    except Exception:
        commit_sha = "unknown"

    return commit_sha, f"Cloned {repository} branch '{branch}' (commit {commit_sha})"
