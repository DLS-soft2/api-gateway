import time
from unittest.mock import MagicMock
import pytest
import jwt as pyjwt
from cryptography.hazmat.primitives.asymmetric import rsa
from app.service.jwt_service import JwtService, _extract_roles
from app.service.jwks_service import JwksService
from tests.unit.security.conftest import make_token, ISSUER, AUDIENCE, KID


def _build_service(rsa_keypair):
    private_key, public_key = rsa_keypair
    mock_jwks = MagicMock(spec=JwksService)
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key
    mock_jwks.get_signing_key.return_value = mock_signing_key
    service = JwtService(mock_jwks, ISSUER, AUDIENCE)
    return service, private_key, mock_jwks


def test_verify_valid_token(rsa_keypair):
    service, private_key, _ = _build_service(rsa_keypair)
    token = make_token(private_key)
    user = service.verify_token(token)
    assert user.sub == "user-123"
    assert user.name == "testuser"
    assert user.email == "test@example.com"
    assert "customer" in user.roles


def test_verify_token_calls_jwks_get_signing_key(rsa_keypair):
    service, private_key, mock_jwks = _build_service(rsa_keypair)
    token = make_token(private_key)
    service.verify_token(token)
    mock_jwks.get_signing_key.assert_called_once_with(token)


def test_verify_token_wrong_issuer(rsa_keypair):
    service, private_key, _ = _build_service(rsa_keypair)
    token = make_token(private_key, claims_override={"iss": "http://evil.example.com/realms/bad"})
    with pytest.raises(pyjwt.InvalidIssuerError):
        service.verify_token(token)


def test_verify_token_wrong_audience(rsa_keypair):
    service, private_key, _ = _build_service(rsa_keypair)
    token = make_token(private_key, claims_override={"aud": "wrong-audience"})
    with pytest.raises(pyjwt.InvalidAudienceError):
        service.verify_token(token)


def test_verify_token_expired(rsa_keypair):
    service, private_key, _ = _build_service(rsa_keypair)
    token = make_token(private_key, claims_override={"exp": int(time.time()) - 3600})
    with pytest.raises(pyjwt.ExpiredSignatureError):
        service.verify_token(token)


def test_verify_token_invalid_signature(rsa_keypair):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = make_token(other_key)
    service, _, _ = _build_service(rsa_keypair)
    with pytest.raises(pyjwt.InvalidSignatureError):
        service.verify_token(token)


def test_verify_token_missing_sub(rsa_keypair):
    service, private_key, _ = _build_service(rsa_keypair)
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    token = pyjwt.encode(claims, private_key, algorithm="RS256", headers={"kid": KID})
    with pytest.raises(pyjwt.MissingRequiredClaimError):
        service.verify_token(token)


def test_extract_roles_realm_access():
    payload = {"realm_access": {"roles": ["admin", "customer"]}}
    assert _extract_roles(payload, "dls-gateway") == ["admin", "customer"]


def test_extract_roles_resource_access_fallback():
    payload = {"resource_access": {"dls-gateway": {"roles": ["courier"]}}}
    assert _extract_roles(payload, "dls-gateway") == ["courier"]


def test_extract_roles_empty_when_none():
    assert _extract_roles({}, "dls-gateway") == []


def test_verify_token_with_resource_access_roles(rsa_keypair):
    service, private_key, _ = _build_service(rsa_keypair)
    token = make_token(private_key, claims_override={
        "realm_access": {"roles": []},
        "resource_access": {AUDIENCE: {"roles": ["restaurant"]}},
    })
    user = service.verify_token(token)
    assert "restaurant" in user.roles


def test_verify_token_no_preferred_username(rsa_keypair):
    service, private_key, _ = _build_service(rsa_keypair)
    token = make_token(private_key, claims_override={"preferred_username": None, "email": None})
    user = service.verify_token(token)
    assert user.sub == "user-123"
    assert user.name is None
    assert user.email is None
