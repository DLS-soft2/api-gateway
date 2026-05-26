from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from app.api.proxy import (
    init_proxy_router,
    router as proxy_router,
    _resolve_route,
)
from app.middleware.auth import require_auth
from app.middleware.request_context import RequestContextMiddleware
from app.models.auth import UserInfo
from app.models.settings import GatewaySettings, RouteConfig
from app.service.proxy_service import ProxyService

FAKE_USER = UserInfo(sub="user-42", name="Test", email="test@example.com", roles=["customer", "admin"])


def _fake_auth():
    """Override require_auth with a dependency that returns FAKE_USER."""
    async def override(request=None):
        return FAKE_USER
    return override


def _build_test_app(
    routes: list[RouteConfig] | None = None,
    forward_response: httpx.Response | None = None,
    auth_override=None,
) -> tuple[FastAPI, AsyncMock]:
    """Build a FastAPI app with proxy router, mock proxy service, and mock auth."""
    settings = GatewaySettings(
        KEYCLOAK_ISSUER_URL="http://kc:8080/realms/dls",
        KEYCLOAK_AUDIENCE="dls-gateway",
        ORDER_SERVICE_BASE_URL="http://order-svc:8000",
        RESTAURANT_SERVICE_BASE_URL="http://restaurant-svc:8000",
        USER_SERVICE_BASE_URL="http://user-svc:8000",
        routes=routes or [
            RouteConfig(prefix="/api/orders", target_env_key="ORDER_SERVICE_BASE_URL"),
            RouteConfig(prefix="/api/restaurants", target_env_key="RESTAURANT_SERVICE_BASE_URL"),
        ],
    )

    mock_forward = AsyncMock(return_value=forward_response or httpx.Response(200, json={"proxied": True}))
    mock_proxy = MagicMock(spec=ProxyService)
    mock_proxy.forward = mock_forward

    init_proxy_router(settings, mock_proxy)

    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)
    test_app.dependency_overrides[require_auth] = auth_override or _fake_auth()
    test_app.include_router(proxy_router)

    return test_app, mock_forward


def test_route_matching_hit():
    routes = [
        RouteConfig(prefix="/api/orders", target_env_key="ORDER_SERVICE_BASE_URL"),
        RouteConfig(prefix="/api/restaurants", target_env_key="RESTAURANT_SERVICE_BASE_URL"),
    ]
    match = _resolve_route("/api/orders/123", routes)
    assert match is not None
    assert match.prefix == "/api/orders"


def test_route_matching_longest_prefix():
    routes = [
        RouteConfig(prefix="/api", target_env_key="ORDER_SERVICE_BASE_URL"),
        RouteConfig(prefix="/api/orders", target_env_key="RESTAURANT_SERVICE_BASE_URL"),
    ]
    match = _resolve_route("/api/orders/123", routes)
    assert match.prefix == "/api/orders"


def test_route_matching_miss():
    routes = [RouteConfig(prefix="/api/orders", target_env_key="ORDER_SERVICE_BASE_URL")]
    match = _resolve_route("/unknown/path", routes)
    assert match is None


def test_unknown_route_returns_404():
    app, _ = _build_test_app(routes=[RouteConfig(prefix="/api/orders", target_env_key="ORDER_SERVICE_BASE_URL")])
    client = TestClient(app)
    resp = client.get("/no/match")
    assert resp.status_code == 404
    assert "No matching route" in resp.json()["detail"]


def test_401_without_token():
    """Proxy returns 401 when auth override is not applied (real auth, no token)."""
    settings = GatewaySettings(
        KEYCLOAK_ISSUER_URL="http://kc:8080/realms/dls",
        KEYCLOAK_AUDIENCE="dls-gateway",
        ORDER_SERVICE_BASE_URL="http://order-svc:8000",
        routes=[RouteConfig(prefix="/api/orders", target_env_key="ORDER_SERVICE_BASE_URL")],
    )
    mock_proxy = MagicMock(spec=ProxyService)
    mock_proxy.forward = AsyncMock(return_value=httpx.Response(200))
    init_proxy_router(settings, mock_proxy)

    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)
    test_app.include_router(proxy_router)
    # No auth override — require_auth will reject missing token
    client = TestClient(test_app)
    resp = client.get("/api/orders/1")
    assert resp.status_code == 401


def test_header_stripping():
    app, mock_forward = _build_test_app()
    client = TestClient(app)
    client.get(
        "/api/orders/1",
        headers={
            "X-User-Id": "attacker",
            "X-User-Roles": "superadmin",
            "X-User-Email": "evil@hack.com",
        },
    )
    call_kwargs = mock_forward.call_args
    forwarded_headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers") or call_kwargs[0][2]
    assert forwarded_headers["x-user-id"] == "user-42"
    assert forwarded_headers["x-user-roles"] == "customer,admin"
    assert forwarded_headers["x-user-email"] == "test@example.com"


def test_header_injection():
    app, mock_forward = _build_test_app()
    client = TestClient(app)
    client.get("/api/orders/1")
    call_kwargs = mock_forward.call_args
    forwarded_headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers") or call_kwargs[0][2]
    assert forwarded_headers["x-user-id"] == "user-42"
    assert forwarded_headers["x-user-roles"] == "customer,admin"
    assert forwarded_headers["x-user-email"] == "test@example.com"
    assert "x-request-id" in forwarded_headers


def test_method_forwarding_post():
    app, mock_forward = _build_test_app()
    client = TestClient(app)
    client.post("/api/orders", json={"item": "pizza"})
    call_kwargs = mock_forward.call_args
    forwarded_method = call_kwargs.kwargs.get("method") or call_kwargs[0][0]
    assert forwarded_method == "POST"


def test_method_forwarding_put():
    app, mock_forward = _build_test_app()
    client = TestClient(app)
    client.put("/api/orders/1", json={"status": "updated"})
    call_kwargs = mock_forward.call_args
    forwarded_method = call_kwargs.kwargs.get("method") or call_kwargs[0][0]
    assert forwarded_method == "PUT"


def test_method_forwarding_delete():
    app, mock_forward = _build_test_app()
    client = TestClient(app)
    client.delete("/api/orders/1")
    call_kwargs = mock_forward.call_args
    forwarded_method = call_kwargs.kwargs.get("method") or call_kwargs[0][0]
    assert forwarded_method == "DELETE"


def test_upstream_status_code_passthrough():
    resp_404 = httpx.Response(404, json={"detail": "not found"})
    app, _ = _build_test_app(forward_response=resp_404)
    client = TestClient(app)
    resp = client.get("/api/orders/999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "not found"
