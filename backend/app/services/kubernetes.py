import base64
import json
import logging
import subprocess
import time
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)


class K8sDeployConfig(BaseModel):
    app_name: str
    image_tag: str
    container_port: int
    namespace: Optional[str] = None
    replicas: int = 1
    env_vars: Dict[str, str] = Field(default_factory=dict)
    subdomain: Optional[str] = None
    base_domain: str = "localtest.me"
    health_path: str = "/health"
    deployment_id: Optional[str] = None
    commit_sha: Optional[str] = None


class K8sDeployResult(BaseModel):
    app_name: str
    namespace: str
    url: str
    ingress_host: str
    replicas: int
    manifests_applied: List[str]
    status: str
    error_message: Optional[str] = None


class KubernetesError(Exception):
    """Raised when Kubernetes deployment or reconciliation fails."""
    pass


class KubernetesService:
    """
    Manages dynamic generation, application, and reconciliation of Kubernetes primitives:
    - Namespace (tenant isolation)
    - Secret (encrypted environment variables)
    - Deployment (pod replicas, rolling update, health probes, non-root UID 10001)
    - Service (ClusterIP internal routing)
    - Ingress (NGINX ingress routing for custom subdomains)
    """

    def __init__(self, kubeconfig_path: Optional[str] = None):
        self.kubeconfig_path = kubeconfig_path or getattr(settings, "KUBECONFIG", None)

    def _clean_name(self, name: str) -> str:
        clean = name.lower().replace("_", "-")
        return "".join(c for c in clean if c.isalnum() or c == "-")

    def resolve_namespace(self, config: K8sDeployConfig) -> str:
        if config.namespace:
            return self._clean_name(config.namespace)
        return f"app-{self._clean_name(config.app_name)}"

    def resolve_subdomain(self, config: K8sDeployConfig) -> str:
        if config.subdomain:
            return self._clean_name(config.subdomain)
        return self._clean_name(config.app_name)

    # -------------------------------------------------------------
    # Manifest Generation
    # -------------------------------------------------------------

    def generate_namespace_manifest(self, namespace: str) -> Dict[str, Any]:
        return {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": namespace,
                "labels": {
                    "deployhub.io/managed-by": "deployhub",
                    "deployhub.io/namespace-type": "application",
                },
            },
        }

    def generate_secret_manifest(self, secret_name: str, namespace: str, env_vars: Dict[str, str]) -> Dict[str, Any]:
        encoded_data = {
            k: base64.b64encode(v.encode("utf-8")).decode("utf-8")
            for k, v in env_vars.items()
        }
        return {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": secret_name,
                "namespace": namespace,
                "labels": {"deployhub.io/managed-by": "deployhub"},
            },
            "type": "Opaque",
            "data": encoded_data,
        }

    def generate_deployment_manifest(self, config: K8sDeployConfig, namespace: str) -> Dict[str, Any]:
        app_name = self._clean_name(config.app_name)
        labels = {
            "app": app_name,
            "app.kubernetes.io/name": app_name,
            "app.kubernetes.io/managed-by": "deployhub",
            "deployhub.io/deployment-id": config.deployment_id or "latest",
            "deployhub.io/commit": (config.commit_sha or "unknown")[:7],
        }

        secret_name = f"{app_name}-env"
        container_spec: Dict[str, Any] = {
            "name": app_name,
            "image": config.image_tag,
            "imagePullPolicy": "IfNotPresent",
            "ports": [{"containerPort": config.container_port, "name": "http"}],
            "env": [
                {"name": "PORT", "value": str(config.container_port)},
            ],
            "resources": {
                "requests": {"cpu": "100m", "memory": "128Mi"},
                "limits": {"cpu": "500m", "memory": "512Mi"},
            },
            "securityContext": {
                "allowPrivilegeEscalation": False,
                "readOnlyRootFilesystem": False,
                "runAsNonRoot": True,
                "runAsUser": 10001,
                "capabilities": {"drop": ["ALL"]},
            },
            "livenessProbe": {
                "httpGet": {"path": config.health_path, "port": "http"},
                "initialDelaySeconds": 5,
                "periodSeconds": 10,
                "timeoutSeconds": 3,
                "failureThreshold": 3,
            },
            "readinessProbe": {
                "httpGet": {"path": config.health_path, "port": "http"},
                "initialDelaySeconds": 2,
                "periodSeconds": 5,
                "timeoutSeconds": 2,
                "failureThreshold": 2,
            },
        }

        if config.env_vars:
            container_spec["envFrom"] = [{"secretRef": {"name": secret_name}}]

        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": app_name,
                "namespace": namespace,
                "labels": labels,
            },
            "spec": {
                "replicas": config.replicas,
                "strategy": {
                    "type": "RollingUpdate",
                    "rollingUpdate": {"maxSurge": 1, "maxUnavailable": 0},
                },
                "selector": {"matchLabels": {"app": app_name}},
                "template": {
                    "metadata": {"labels": labels},
                    "spec": {
                        "securityContext": {
                            "runAsNonRoot": True,
                            "runAsUser": 10001,
                            "fsGroup": 10001,
                        },
                        "containers": [container_spec],
                    },
                },
            },
        }

    def generate_service_manifest(self, config: K8sDeployConfig, namespace: str) -> Dict[str, Any]:
        app_name = self._clean_name(config.app_name)
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": app_name,
                "namespace": namespace,
                "labels": {
                    "app": app_name,
                    "deployhub.io/managed-by": "deployhub",
                },
            },
            "spec": {
                "type": "ClusterIP",
                "selector": {"app": app_name},
                "ports": [
                    {
                        "name": "http",
                        "port": config.container_port,
                        "targetPort": "http",
                        "protocol": "TCP",
                    }
                ],
            },
        }

    def generate_ingress_manifest(self, config: K8sDeployConfig, namespace: str) -> Dict[str, Any]:
        app_name = self._clean_name(config.app_name)
        subdomain = self.resolve_subdomain(config)
        ingress_host = f"{subdomain}.{config.base_domain}"

        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": app_name,
                "namespace": namespace,
                "labels": {
                    "app": app_name,
                    "deployhub.io/managed-by": "deployhub",
                },
                "annotations": {
                    "kubernetes.io/ingress.class": "nginx",
                    "nginx.ingress.kubernetes.io/proxy-body-size": "50m",
                    "nginx.ingress.kubernetes.io/proxy-read-timeout": "120",
                },
            },
            "spec": {
                "ingressClassName": "nginx",
                "rules": [
                    {
                        "host": ingress_host,
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {
                                        "service": {
                                            "name": app_name,
                                            "port": {"number": config.container_port},
                                        }
                                    },
                                }
                            ]
                        },
                    }
                ],
            },
        }

    def generate_manifest_bundle(self, config: K8sDeployConfig) -> Dict[str, Dict[str, Any]]:
        namespace = self.resolve_namespace(config)
        app_name = self._clean_name(config.app_name)

        bundle = {
            "namespace": self.generate_namespace_manifest(namespace),
            "deployment": self.generate_deployment_manifest(config, namespace),
            "service": self.generate_service_manifest(config, namespace),
            "ingress": self.generate_ingress_manifest(config, namespace),
        }

        if config.env_vars:
            bundle["secret"] = self.generate_secret_manifest(f"{app_name}-env", namespace, config.env_vars)

        return bundle

    def generate_yaml_bundle(self, config: K8sDeployConfig) -> str:
        bundle = self.generate_manifest_bundle(config)
        docs = [yaml.dump(m, sort_keys=False) for m in bundle.values()]
        return "---\n".join(docs)

    # -------------------------------------------------------------
    # Cluster Application & Lifecycle
    # -------------------------------------------------------------

    def apply_manifests(self, config: K8sDeployConfig) -> K8sDeployResult:
        """Applies generated manifests to the Kubernetes cluster."""
        yaml_content = self.generate_yaml_bundle(config)
        namespace = self.resolve_namespace(config)
        subdomain = self.resolve_subdomain(config)
        ingress_host = f"{subdomain}.{config.base_domain}"
        url = f"http://{ingress_host}"

        cmd = ["kubectl", "apply", "-f", "-"]
        if self.kubeconfig_path:
            cmd.extend(["--kubeconfig", self.kubeconfig_path])

        try:
            proc = subprocess.run(
                cmd,
                input=yaml_content,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode != 0:
                err = proc.stderr.strip() or proc.stdout.strip()
                raise KubernetesError(f"kubectl apply failed: {err}")

            applied_kinds = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
            return K8sDeployResult(
                app_name=config.app_name,
                namespace=namespace,
                url=url,
                ingress_host=ingress_host,
                replicas=config.replicas,
                manifests_applied=applied_kinds,
                status="APPLIED",
            )
        except subprocess.TimeoutExpired:
            raise KubernetesError("kubectl apply timed out after 60s")
        except FileNotFoundError:
            raise KubernetesError("kubectl binary not found in PATH")
        except Exception as e:
            if isinstance(e, KubernetesError):
                raise
            raise KubernetesError(f"Failed to apply Kubernetes manifests: {str(e)}")

    def wait_for_rollout(self, app_name: str, namespace: str, timeout_seconds: int = 120) -> bool:
        """Awaits successful deployment rollout in the cluster."""
        clean = self._clean_name(app_name)
        cmd = [
            "kubectl",
            "rollout",
            "status",
            f"deployment/{clean}",
            "-n",
            namespace,
            f"--timeout={timeout_seconds}s",
        ]
        if self.kubeconfig_path:
            cmd.extend(["--kubeconfig", self.kubeconfig_path])

        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode == 0

    def get_pod_logs(self, app_name: str, namespace: str, tail: int = 100) -> str:
        """Fetches pod standard output and error logs."""
        clean = self._clean_name(app_name)
        cmd = [
            "kubectl",
            "logs",
            f"-l=app={clean}",
            "-n",
            namespace,
            f"--tail={tail}",
            "--all-containers=true",
        ]
        if self.kubeconfig_path:
            cmd.extend(["--kubeconfig", self.kubeconfig_path])

        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.stdout or proc.stderr

    def delete_app(self, app_name: str, namespace: str) -> bool:
        """Deletes the application namespace and its associated resources."""
        cmd = ["kubectl", "delete", "namespace", namespace, "--ignore-not-found=true"]
        if self.kubeconfig_path:
            cmd.extend(["--kubeconfig", self.kubeconfig_path])

        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode == 0


kubernetes_service = KubernetesService()
