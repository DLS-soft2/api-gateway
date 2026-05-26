import pytest
import httpx
from fastapi import HTTPException
from app.service.proxy_service import ProxyService


@pytest.fixture()
def mock_transport():
    """Provide an httpx.MockTransport factory for test responses."""
    def _factory(handler):
        return httpx.MockTransport(handler)
    return _factory


def _make_service(transport: httpx.MockTransport) -> ProxyService:
    client = httpx.AsyncClient(transport=transport)
    return ProxyService(client)


@pytest.mark.asyncio
async def test_forward_success(mock_transport):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    service = _make_service(mock_transport(handler))
    resp = await service.forward("GET", "http://backend/test", {})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_forward_preserves_method_and_body(mock_transport):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"method": request.method, "body": request.content.decode()})

    service = _make_service(mock_transport(handler))
    resp = await service.forward("POST", "http://backend/items", {"content-type": "application/json"}, b'{"x":1}')
    assert resp.status_code == 200
    body = resp.json()
    assert body["method"] == "POST"
    assert body["body"] == '{"x":1}'


@pytest.mark.asyncio
async def test_forward_timeout_raises_504():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    service = _make_service(httpx.MockTransport(handler))
    with pytest.raises(HTTPException) as exc_info:
        await service.forward("GET", "http://backend/slow", {})
    assert exc_info.value.status_code == 504


@pytest.mark.asyncio
async def test_forward_connect_error_raises_502():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    service = _make_service(httpx.MockTransport(handler))
    with pytest.raises(HTTPException) as exc_info:
        await service.forward("GET", "http://backend/down", {})
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_forward_upstream_4xx_passthrough(mock_transport):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "bad input"})

    service = _make_service(mock_transport(handler))
    resp = await service.forward("POST", "http://backend/validate", {})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "bad input"


@pytest.mark.asyncio
async def test_forward_upstream_5xx_passthrough(mock_transport):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "overloaded"})

    service = _make_service(mock_transport(handler))
    resp = await service.forward("GET", "http://backend/busy", {})
    assert resp.status_code == 503
    assert resp.json()["error"] == "overloaded"
