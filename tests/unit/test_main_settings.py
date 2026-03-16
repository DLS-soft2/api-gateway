import pytest
from pydantic import ValidationError
from app.models.settings import GatewaySettings, load_settings


def test_load_settings_from_env(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_ISSUER_URL", "http://kc:8080/realms/test")
    monkeypatch.setenv("KEYCLOAK_AUDIENCE", "test-client")
    monkeypatch.setenv("USER_SERVICE_BASE_URL", "http://user:8001")
    s = load_settings()
    assert s.KEYCLOAK_ISSUER_URL == "http://kc:8080/realms/test"
    assert s.KEYCLOAK_AUDIENCE == "test-client"
    assert s.USER_SERVICE_BASE_URL == "http://user:8001"
    assert s.PROXY_TIMEOUT_SECONDS == 30.0


def test_settings_fails_without_keycloak_issuer(monkeypatch):
    monkeypatch.delenv("KEYCLOAK_ISSUER_URL", raising=False)
    monkeypatch.setenv("KEYCLOAK_AUDIENCE", "aud")
    monkeypatch.setenv("USER_SERVICE_BASE_URL", "http://user:8001")
    with pytest.raises(ValidationError):
        GatewaySettings()


def test_settings_fails_without_keycloak_audience(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_ISSUER_URL", "http://kc:8080/realms/test")
    monkeypatch.delenv("KEYCLOAK_AUDIENCE", raising=False)
    monkeypatch.setenv("USER_SERVICE_BASE_URL", "http://user:8001")
    with pytest.raises(ValidationError):
        GatewaySettings()


def test_settings_fails_without_user_service_url(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_ISSUER_URL", "http://kc:8080/realms/test")
    monkeypatch.setenv("KEYCLOAK_AUDIENCE", "aud")
    monkeypatch.delenv("USER_SERVICE_BASE_URL", raising=False)
    with pytest.raises(ValidationError):
        GatewaySettings()


def test_settings_custom_timeout(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_ISSUER_URL", "http://kc:8080/realms/test")
    monkeypatch.setenv("KEYCLOAK_AUDIENCE", "aud")
    monkeypatch.setenv("USER_SERVICE_BASE_URL", "http://user:8001")
    monkeypatch.setenv("PROXY_TIMEOUT_SECONDS", "10.0")
    s = GatewaySettings()
    assert s.PROXY_TIMEOUT_SECONDS == 10.0
