import json
import time
import pytest
import jwt as pyjwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

ISSUER = "http://localhost:8080/realms/dls"
AUDIENCE = "dls-gateway"
KID = "test-kid-1"


@pytest.fixture()
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture()
def jwks_data(rsa_keypair):  # pylint: disable=redefined-outer-name
    _, public_key = rsa_keypair
    jwk_dict = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk_dict["kid"] = KID
    jwk_dict["use"] = "sig"
    jwk_dict["alg"] = "RS256"
    return {"keys": [jwk_dict]}


def make_token(private_key, claims_override=None, kid=KID):
    claims = {
        "sub": "user-123",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "realm_access": {"roles": ["customer"]},
        "preferred_username": "testuser",
        "email": "test@example.com",
    }
    if claims_override:
        claims.update(claims_override)
    return pyjwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})
