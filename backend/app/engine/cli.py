import argparse
import json
import sys
from app.engine.models import DeploymentConfig, DeploymentStatus
from app.engine.orchestrator import DeploymentOrchestrator
from app.engine.runner import get_container_logs, stop_container


def print_banner():
    banner = """
  ╔═══════════════════════════════════════════════════╗
  ║           ☁️  DeployHub Engine CLI  ☁️            ║
  ║  "From Source Code to Production URL on Docker"  ║
  ╚═══════════════════════════════════════════════════╝
    """
    print(banner)


def cmd_deploy(args):
    orchestrator = DeploymentOrchestrator()
    config = DeploymentConfig(
        repository=args.repo,
        branch=args.branch,
        port=args.port,
        project_name=args.name,
    )

    def on_status(stage: DeploymentStatus, msg: str):
        color = "\033[36m"
        if stage == DeploymentStatus.RUNNING:
            color = "\033[32m"
        elif stage == DeploymentStatus.FAILED:
            color = "\033[31m"
        reset = "\033[0m"
        print(f"{color}{msg}{reset}", flush=True)

    print(f"\n🚀 Initiating deployment for: {args.repo} (branch: {args.branch})\n")
    result = orchestrator.deploy(config, on_status_change=on_status)

    print("\n" + "=" * 60)
    print(f"Deployment Result: {result.status.value}")
    print("=" * 60)
    if result.status == DeploymentStatus.RUNNING:
        print(f"✨ Application URL : {result.url}")
        print(f"🐳 Container Name  : {result.container_name}")
        print(f"🏷️  Docker Image    : {result.image}")
        print(f"🔖 Commit SHA      : {result.commit_sha}")
        sys.exit(0)
    else:
        print(f"❌ Failure Stage   : {result.failure_stage}")
        print(f"⚠️  Error Message   : {result.error_message}")
        sys.exit(1)


def cmd_stop(args):
    print(f"Stopping container: {args.container}")
    success = stop_container(args.container)
    if success:
        print(f"Successfully stopped and removed {args.container}")
    else:
        print(f"Failed or container not found: {args.container}")


def cmd_logs(args):
    logs = get_container_logs(args.container, tail=args.tail)
    print(logs)


def main():
    parser = argparse.ArgumentParser(description="DeployHub Deployment Engine CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Deploy
    deploy_parser = subparsers.add_parser("deploy", help="Deploy a project repository")
    deploy_parser.add_argument("repo", help="Repository URL or local directory path")
    deploy_parser.add_argument("--branch", default="main", help="Git branch to clone")
    deploy_parser.add_argument("--port", type=int, default=None, help="Application port")
    deploy_parser.add_argument("--name", default=None, help="Project name")
    deploy_parser.set_defaults(func=cmd_deploy)

    # Stop
    stop_parser = subparsers.add_parser("stop", help="Stop a deployed container")
    stop_parser.add_argument("container", help="Container name or ID")
    stop_parser.set_defaults(func=cmd_stop)

    # Logs
    logs_parser = subparsers.add_parser("logs", help="Get logs of a container")
    logs_parser.add_argument("container", help="Container name or ID")
    logs_parser.add_argument("--tail", type=int, default=100, help="Number of lines")
    logs_parser.set_defaults(func=cmd_logs)

    args = parser.parse_args()
    print_banner()
    args.func(args)


if __name__ == "__main__":
    main()
