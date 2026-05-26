import os
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.proxy import init_proxy_router, router as proxy_router
from app.middleware.auth import init_auth_dependency
from app.middleware.request_context import RequestContextMiddleware
from app.models.settings import GatewaySettings, RouteConfig
from app.service.jwt_service import JwtService
from app.service.jwks_service import JwksService
from app.service.proxy_service import ProxyService

KEYCLOAK_BASE = os.environ.get("KEYCLOAK_URL", "http://localhost:8080")
ISSUER = f"{KEYCLOAK_BASE}/realms/dls"
AUDIENCE = "dls-gateway"
TOKEN_ENDPOINT = f"{ISSUER}/protocol/openid-connect/token"
UPSTREAM_BASE = "http://mock-upstream:9000"


@dataclass
class UpstreamMock:
    """Configurable mock upstream that captures forwarded requests."""
    response_status: int = 200
    response_body: bytes = b'{"upstream": true}'
    response_content_type: str = "application/json"
    captured: list = field(default_factory=list)
    handler: Callable[[httpx.Request], httpx.Response] | None = None

    def handle(self, request: httpx.Request) -> httpx.Response:
        """Record the request and return the configured response."""
        self.captured.append({
            "method": request.method,
            "url": str(request.url),
            "headers": {k: v for k, v in request.headers.items()},
            "body": request.content,
        })
        if self.handler:
            return self.handler(request)
        return httpx.Response(
            status_code=self.response_status,
            content=self.response_body,
            headers={"content-type": self.response_content_type},
        )

    @property
    def last_request(self) -> dict:
        """Return the most recently captured request."""
        return self.captured[-1]


def _keycloak_is_reachable() -> bool:
    """Check whether Keycloak is accepting connections."""
    try:
        resp = httpx.get(f"{KEYCLOAK_BASE}/realms/dls", timeout=3.0)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session", autouse=True)
def keycloak_available():
    """Skip all integration tests if Keycloak is not running."""
    if not _keycloak_is_reachable():
        pytest.skip("Keycloak not available")


def get_token(username: str, password: str) -> str:
    """Obtain a real access token from Keycloak via resource-owner password grant."""
    resp = httpx.post(
        TOKEN_ENDPOINT,
        data={
            "grant_type": "password",
            "client_id": AUDIENCE,
            "username": username,
            "password": password,
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def customer_token(keycloak_available):  # pylint: disable=redefined-outer-name,unused-argument
    """Real Keycloak JWT for the testuser (customer role)."""
    return get_token("testuser", "password")


@pytest.fixture(scope="session")
def courier_token(keycloak_available):  # pylint: disable=redefined-outer-name,unused-argument
    """Real Keycloak JWT for the testcourier (courier role)."""
    return get_token("testcourier", "password")


@pytest.fixture()
def upstream_mock() -> UpstreamMock:
    """Provide a configurable mock upstream for each test."""
    return UpstreamMock()


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
    gateway_settings, upstream_mock,
):  # pylint: disable=redefined-outer-name
    """Build the gateway app with REAL JwksService/JwtService and mock upstream transport.

    JwksService points at the real Keycloak JWKS endpoint so tokens are validated
    against Keycloak's actual signing keys. The proxy still uses MockTransport for
    upstream services since they may not be running.
    """
    jwks_service = JwksService(ISSUER)
    jwt_service = JwtService(jwks_service, ISSUER, AUDIENCE)
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
