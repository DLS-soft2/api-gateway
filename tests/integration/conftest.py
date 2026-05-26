import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio
import jwt as pyjwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.proxy import init_proxy_router, router as proxy_router
from app.middleware.auth import init_auth_dependency
from app.middleware.request_context import RequestContextMiddleware
from app.models.settings import GatewaySettings, RouteConfig
from app.service.jwt_service import JwtService
from app.service.jwks_service import JwksService
from app.service.proxy_service import ProxyService

ISSUER = "http://localhost:8080/realms/dls"
AUDIENCE = "dls-gateway"
KID = "integration-test-kid"
UPSTREAM_BASE = "http://mock-upstream:9000"


@dataclass
class CapturedUpstreamRequest:
    """Stores details of a request forwarded to the mock upstream."""
    method: str
    url: str
    headers: dict[str, str]
    body: bytes


@dataclass
class UpstreamMock:
    """Configurable mock upstream that captures forwarded requests."""
    response_status: int = 200
    response_body: bytes = b'{"upstream": true}'
    response_content_type: str = "application/json"
    captured: list[CapturedUpstreamRequest] = field(default_factory=list)
    handler: Callable[[httpx.Request], httpx.Response] | None = None

    def handle(self, request: httpx.Request) -> httpx.Response:
        """Record the request and return the configured response."""
        self.captured.append(CapturedUpstreamRequest(
            method=request.method,
            url=str(request.url),
            headers={k: v for k, v in request.headers.items()},
            body=request.content,
        ))
        if self.handler:
            return self.handler(request)
        return httpx.Response(
            status_code=self.response_status,
            content=self.response_body,
            headers={"content-type": self.response_content_type},
        )

    @property
    def last_request(self) -> CapturedUpstreamRequest:
        """Return the most recently captured request."""
        return self.captured[-1]


@pytest.fixture(scope="session")
def rsa_keypair():
    """Generate a single RSA keypair for the entire test session."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture(scope="session")
def jwks_data(rsa_keypair):  # pylint: disable=redefined-outer-name
    """Build a JWKS JSON structure from the session RSA public key."""
    _, public_key = rsa_keypair
    jwk_dict = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk_dict["kid"] = KID
    jwk_dict["use"] = "sig"
    jwk_dict["alg"] = "RS256"
    return {"keys": [jwk_dict]}


def make_token(
    private_key,
    claims_override: dict | None = None,
    kid: str = KID,
) -> str:
    """Create a signed JWT with sensible defaults, optionally overriding claims."""
    claims = {
        "sub": "user-integration-1",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "realm_access": {"roles": ["customer"]},
        "preferred_username": "integrationuser",
        "email": "integration@example.com",
    }
    if claims_override:
        claims.update(claims_override)
    return pyjwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


@pytest.fixture()
def token_factory(rsa_keypair):  # pylint: disable=redefined-outer-name
    """Return a callable that creates signed JWTs with optional claim overrides."""
    private_key, _ = rsa_keypair
    def _factory(claims_override: dict | None = None) -> str:
        return make_token(private_key, claims_override)
    return _factory


@pytest.fixture()
def upstream_mock() -> UpstreamMock:
    """Provide a configurable mock upstream for each test."""
    return UpstreamMock()


def _build_mock_jwks(rsa_keypair) -> JwksService:
    """Create a JwksService mock that returns the test public key."""
    _, public_key = rsa_keypair
    mock_jwks = MagicMock(spec=JwksService)
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key
    mock_jwks.get_signing_key.return_value = mock_signing_key
    return mock_jwks


@pytest.fixture()
def gateway_settings() -> GatewaySettings:
    """Settings with routes pointing at the mock upstream."""
    return GatewaySettings(
        KEYCLOAK_ISSUER_URL=ISSUER,
        KEYCLOAK_AUDIENCE=AUDIENCE,
        PROXY_TIMEOUT_SECONDS=5.0,
        ORDER_SERVICE_BASE_URL=UPSTREAM_BASE,
        RESTAURANT_SERVICE_BASE_URL=UPSTREAM_BASE,
        COURIER_SERVICE_BASE_URL=UPSTREAM_BASE,
        PAYMENT_SERVICE_BASE_URL=UPSTREAM_BASE,
        NOTIFICATION_SERVICE_BASE_URL=UPSTREAM_BASE,
        USER_SERVICE_BASE_URL=UPSTREAM_BASE,
        routes=[
            RouteConfig(prefix="/api/orders", target_env_key="ORDER_SERVICE_BASE_URL"),
            RouteConfig(prefix="/api/restaurants", target_env_key="RESTAURANT_SERVICE_BASE_URL"),
        ],
    )


@pytest_asyncio.fixture()
async def integration_app(
    rsa_keypair, gateway_settings, upstream_mock,
):  # pylint: disable=redefined-outer-name
    """Build the real gateway app with mocked JWKS and mock upstream transport.

    Mirrors the wiring from app/main.py: RequestContextMiddleware, real auth
    dependency, health router, and proxy router. The only mocked externals are
    JWKS key resolution (mock JwksService) and the upstream HTTP transport
    (httpx.MockTransport). The proxy service and router are wired eagerly
    because httpx.ASGITransport does not trigger ASGI lifespan events.
    """
    mock_jwks = _build_mock_jwks(rsa_keypair)
    jwt_service = JwtService(mock_jwks, ISSUER, AUDIENCE)
    init_auth_dependency(jwt_service)

    transport = httpx.MockTransport(upstream_mock.handle)
    http_client = httpx.AsyncClient(
        transport=transport,
        timeout=gateway_settings.PROXY_TIMEOUT_SECONDS,
    )
    proxy_service = ProxyService(http_client)
    init_proxy_router(gateway_settings, proxy_service)

    test_app = FastAPI(title="Integration Test Gateway")
    test_app.add_middleware(RequestContextMiddleware)
    test_app.include_router(health_router)
    test_app.include_router(proxy_router)

    yield test_app

    await http_client.aclose()


@pytest_asyncio.fixture()
async def client(integration_app):  # pylint: disable=redefined-outer-name
    """Async test client that exercises the full middleware stack."""
    transport = httpx.ASGITransport(app=integration_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
