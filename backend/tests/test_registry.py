import pytest
from app.services.registry import ContainerRegistryService, RegistryError


def test_format_image_tag_local():
    svc = ContainerRegistryService(registry_url="", username="", token="")
    tag = svc.format_image_tag("my_api", "123456789")
    assert tag == "deployhub/my-api:1234567"


def test_format_image_tag_ghcr():
    svc = ContainerRegistryService(
        registry_url="ghcr.io",
        username="my-org",
        token="token123",
    )
    tag = svc.format_image_tag("weather-service", "abcdef12")
    assert tag == "ghcr.io/my-org/weather-service:abcdef1"


def test_unconfigured_push_fallback():
    svc = ContainerRegistryService(registry_url="", username="", token="")
    ok, msg = svc.push_image("deployhub/app:abc")
    assert ok is True
    assert "retained in local Docker cache" in msg


def test_unconfigured_login_fallback():
    svc = ContainerRegistryService(registry_url="", username="", token="")
    ok, msg = svc.login()
    assert ok is False
    assert "not configured" in msg
