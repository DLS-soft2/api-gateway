from unittest.mock import MagicMock
import pytest
import jwt as pyjwt
from app.service.jwks_service import JwksService
from tests.unit.security.conftest import make_token, ISSUER


def test_constructs_jwks_url():
    svc = JwksService("http://kc:8080/realms/test")
    assert svc._jwks_url == (  # pylint: disable=protected-access
        "http://kc:8080/realms/test/protocol/openid-connect/certs"
    )


def test_constructs_jwks_url_strips_trailing_slash():
    svc = JwksService("http://kc:8080/realms/test/")
    assert svc._jwks_url == (  # pylint: disable=protected-access
        "http://kc:8080/realms/test/protocol/openid-connect/certs"
    )


def _mock_jwks_client(service):
    mock_client = MagicMock()
    service._jwks_client = mock_client  # pylint: disable=protected-access
    return mock_client


def test_get_signing_key_cache_hit(rsa_keypair):
    private_key, _ = rsa_keypair
    token = make_token(private_key)
    service = JwksService(ISSUER)
    mock_client = _mock_jwks_client(service)
    mock_key = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = mock_key
    result = service.get_signing_key(token)
    assert result is mock_key
    mock_client.get_signing_key_from_jwt.assert_called_once_with(token)
    mock_client.fetch_data.assert_not_called()


def test_get_signing_key_refresh_on_unknown_kid(rsa_keypair):
    private_key, _ = rsa_keypair
    token = make_token(private_key, kid="unknown-kid")
    service = JwksService(ISSUER)
    mock_client = _mock_jwks_client(service)
    mock_key = MagicMock()
    mock_client.get_signing_key_from_jwt.side_effect = [
        pyjwt.PyJWKClientError("kid not found"),
        mock_key,
    ]
    result = service.get_signing_key(token)
    assert result is mock_key
    assert mock_client.get_signing_key_from_jwt.call_count == 2
    mock_client.fetch_data.assert_called_once()


def test_get_signing_key_refresh_fails_raises(rsa_keypair):
    private_key, _ = rsa_keypair
    token = make_token(private_key, kid="bad-kid")
    service = JwksService(ISSUER)
    mock_client = _mock_jwks_client(service)
    mock_client.get_signing_key_from_jwt.side_effect = (
        pyjwt.PyJWKClientError("kid not found")
    )
    with pytest.raises(pyjwt.PyJWKClientError):
        service.get_signing_key(token)
    mock_client.fetch_data.assert_called_once()
