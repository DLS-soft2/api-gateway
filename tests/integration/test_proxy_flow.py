import httpx
import pytest


@pytest.mark.asyncio
async def test_valid_keycloak_token_forwards_to_upstream(client, customer_token, upstream_mock):
    """A real Keycloak JWT results in the request being forwarded to upstream."""
    resp = await client.get(
        "/api/orders/123",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"upstream": True}
    assert len(upstream_mock.captured) == 1
    assert "/api/orders/123" in upstream_mock.last_request["url"]


@pytest.mark.asyncio
async def test_expired_token_returns_401(client, upstream_mock):
    """A deliberately invalid token is rejected with 401."""
    resp = await client.get(
        "/api/orders/1",
        headers={"Authorization": "Bearer expired.invalid.token"},
    )
    assert resp.status_code == 401
    assert len(upstream_mock.captured) == 0


@pytest.mark.asyncio
async def test_missing_token_returns_401(client, upstream_mock):
    """A request with no Authorization header is rejected with 401."""
    resp = await client.get("/api/orders/1")
    assert resp.status_code == 401
    assert len(upstream_mock.captured) == 0


@pytest.mark.asyncio
async def test_unknown_route_returns_404(client, customer_token, upstream_mock):
    """A request to an unconfigured route prefix returns 404."""
    resp = await client.get(
        "/api/unknown/resource",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 404
    assert "No matching route" in resp.json()["detail"]
    assert len(upstream_mock.captured) == 0


@pytest.mark.asyncio
async def test_upstream_timeout_returns_504(client, customer_token, upstream_mock):
    """When the upstream times out, the gateway returns 504."""
    def timeout_handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("upstream timed out")

    upstream_mock.handler = timeout_handler
    resp = await client.get(
        "/api/orders/1",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 504


@pytest.mark.asyncio
async def test_upstream_5xx_status_passthrough(client, customer_token, upstream_mock):
    """An upstream 503 is passed through to the client as-is."""
    upstream_mock.response_status = 503
    upstream_mock.response_body = b'{"error": "service unavailable"}'

    resp = await client.get(
        "/api/orders/1",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert resp.status_code == 503
    assert resp.json()["error"] == "service unavailable"
