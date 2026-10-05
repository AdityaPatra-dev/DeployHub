import pytest
import yaml
from app.services.kubernetes import K8sDeployConfig, KubernetesService


@pytest.fixture
def k8s_service():
    return KubernetesService()


def test_generate_manifest_bundle_structure(k8s_service):
    config = K8sDeployConfig(
        app_name="weather-api",
        image_tag="ghcr.io/deployhub/weather-api:a81f92d",
        container_port=8000,
        env_vars={"DATABASE_URL": "postgres://localhost", "API_KEY": "secret123"},
        subdomain="weather",
        base_domain="deployhub.live",
        commit_sha="a81f92df001",
        deployment_id="42",
    )

    bundle = k8s_service.generate_manifest_bundle(config)

    # 1. Assert all core primitives exist
    assert "namespace" in bundle
    assert "secret" in bundle
    assert "deployment" in bundle
    assert "service" in bundle
    assert "ingress" in bundle

    # 2. Namespace assertion
    assert bundle["namespace"]["metadata"]["name"] == "app-weather-api"

    # 3. Secret assertion
    secret = bundle["secret"]
    assert secret["metadata"]["name"] == "weather-api-env"
    assert "DATABASE_URL" in secret["data"]
    assert "API_KEY" in secret["data"]

    # 4. Deployment assertions (Security, Probes, Resources)
    dep = bundle["deployment"]
    spec = dep["spec"]
    assert spec["replicas"] == 1
    assert spec["strategy"]["rollingUpdate"]["maxSurge"] == 1
    assert spec["strategy"]["rollingUpdate"]["maxUnavailable"] == 0

    pod_spec = spec["template"]["spec"]
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    assert pod_spec["securityContext"]["runAsUser"] == 10001

    container = pod_spec["containers"][0]
    assert container["image"] == "ghcr.io/deployhub/weather-api:a81f92d"
    assert container["resources"]["limits"]["memory"] == "512Mi"
    assert container["resources"]["limits"]["cpu"] == "500m"
    assert container["livenessProbe"]["httpGet"]["path"] == "/health"
    assert container["readinessProbe"]["httpGet"]["path"] == "/health"
    assert container["securityContext"]["allowPrivilegeEscalation"] is False

    # 5. Service assertion
    svc = bundle["service"]
    assert svc["spec"]["type"] == "ClusterIP"
    assert svc["spec"]["ports"][0]["port"] == 8000

    # 6. Ingress assertion
    ing = bundle["ingress"]
    assert ing["spec"]["ingressClassName"] == "nginx"
    assert ing["spec"]["rules"][0]["host"] == "weather.deployhub.live"
    assert ing["spec"]["rules"][0]["http"]["paths"][0]["backend"]["service"]["name"] == "weather-api"


def test_generate_yaml_bundle_validity(k8s_service):
    config = K8sDeployConfig(
        app_name="simple-app",
        image_tag="deployhub/simple-app:latest",
        container_port=3000,
    )
    yaml_str = k8s_service.generate_yaml_bundle(config)
    assert isinstance(yaml_str, str)

    # Validate that it parses as multi-document YAML
    docs = list(yaml.safe_load_all(yaml_str))
    assert len(docs) == 4  # Namespace, Deployment, Service, Ingress (no secret since no env_vars)
    kinds = [d["kind"] for d in docs]
    assert kinds == ["Namespace", "Deployment", "Service", "Ingress"]


def test_custom_namespace_and_subdomain(k8s_service):
    config = K8sDeployConfig(
        app_name="portal",
        image_tag="deployhub/portal:1.0",
        container_port=8080,
        namespace="custom-tenant",
        subdomain="custom-portal",
        base_domain="localtest.me",
    )
    ns = k8s_service.resolve_namespace(config)
    sub = k8s_service.resolve_subdomain(config)
    assert ns == "custom-tenant"
    assert sub == "custom-portal"
