import time
from unittest.mock import MagicMock
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from app.middleware.auth import init_auth_dependency, require_auth
from app.models.auth import UserInfo
from app.service.jwt_service import JwtService
from app.service.jwks_service import JwksService
from tests.unit.security.conftest import make_token, ISSUER, AUDIENCE


def _build_test_app(rsa_keypair):
    private_key, public_key = rsa_keypair
    mock_jwks = MagicMock(spec=JwksService)
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key
    mock_jwks.get_signing_key.return_value = mock_signing_key
    jwt_service = JwtService(mock_jwks, ISSUER, AUDIENCE)
    init_auth_dependency(jwt_service)
    test_app = FastAPI()

    @test_app.get("/protected")
    async def protected(
        request: Request, user: UserInfo = Depends(require_auth),
    ):
        has_state = hasattr(request.state, "user_info")
        return {"sub": user.sub, "roles": user.roles, "has_state": has_state}

    return test_app, private_key


def test_missing_bearer_returns_401(rsa_keypair):
    test_app, _ = _build_test_app(rsa_keypair)
    client = TestClient(test_app)
    response = client.get("/protected")
    assert response.status_code == 401
    assert "Missing bearer token" in response.json()["detail"]


def test_malformed_token_returns_401(rsa_keypair):
    test_app, _ = _build_test_app(rsa_keypair)
    client = TestClient(test_app)
    response = client.get("/protected", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_valid_token_returns_user_info(rsa_keypair):
    test_app, private_key = _build_test_app(rsa_keypair)
    client = TestClient(test_app)
    token = make_token(private_key)
    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["sub"] == "user-123"
    assert "customer" in body["roles"]
    assert body["has_state"] is True


def test_expired_token_returns_401(rsa_keypair):
    test_app, private_key = _build_test_app(rsa_keypair)
    client = TestClient(test_app)
    token = make_token(private_key, claims_override={"exp": int(time.time()) - 3600})
    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_wrong_issuer_returns_401(rsa_keypair):
    test_app, private_key = _build_test_app(rsa_keypair)
    client = TestClient(test_app)
    token = make_token(private_key, claims_override={"iss": "http://evil.example.com/realms/bad"})
    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "issuer" in response.json()["detail"].lower()


def test_wrong_audience_returns_401(rsa_keypair):
    test_app, private_key = _build_test_app(rsa_keypair)
    client = TestClient(test_app)
    token = make_token(private_key, claims_override={"aud": "wrong-audience"})
    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "audience" in response.json()["detail"].lower()


def test_user_info_stored_on_request_state(rsa_keypair):
    test_app, private_key = _build_test_app(rsa_keypair)
    client = TestClient(test_app)
    token = make_token(private_key)
    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["has_state"] is True
