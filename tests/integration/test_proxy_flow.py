import time
import httpx
import pytest


@pytest.mark.asyncio
async def test_valid_token_forwards_to_upstream(client, token_factory, upstream_mock):
    """A valid JWT results in the request being forwarded to the upstream service."""
    token = token_factory()
    resp = await client.get(
        "/api/orders/123",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"upstream": True}
    assert len(upstream_mock.captured) == 1
    assert "/api/orders/123" in upstream_mock.last_request.url


@pytest.mark.asyncio
async def test_expired_token_returns_401(client, token_factory, upstream_mock):
    """An expired JWT is rejected with 401 and the request never reaches upstream."""
    token = token_factory({"exp": int(time.time()) - 3600})
    resp = await client.get(
        "/api/orders/1",
        headers={"Authorization": f"Bearer {token}"},
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
async def test_unknown_route_returns_404(client, token_factory, upstream_mock):
    """A request to an unconfigured route prefix returns 404."""
    token = token_factory()
    resp = await client.get(
        "/api/unknown/resource",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert "No matching route" in resp.json()["detail"]
    assert len(upstream_mock.captured) == 0


@pytest.mark.asyncio
async def test_upstream_timeout_returns_504(
    client, token_factory, upstream_mock,
):
    """When the upstream times out, the gateway returns 504."""
    def timeout_handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("upstream timed out")

    upstream_mock.handler = timeout_handler
    token = token_factory()
    resp = await client.get(
        "/api/orders/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 504


@pytest.mark.asyncio
async def test_upstream_5xx_status_passthrough(
    client, token_factory, upstream_mock,
):
    """An upstream 503 is passed through to the client as-is."""
    upstream_mock.response_status = 503
    upstream_mock.response_body = b'{"error": "service unavailable"}'

    token = token_factory()
    resp = await client.get(
        "/api/orders/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 503
    assert resp.json()["error"] == "service unavailable"
