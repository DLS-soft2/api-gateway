import httpx
from fastapi import HTTPException


class ProxyService:
    """Forwards HTTP requests to downstream services via httpx."""

    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def forward(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        content: bytes | None = None,
    ) -> httpx.Response:
        """Forward a request to the given URL and return the upstream response."""
        try:
            return await self._client.request(
                method=method,
                url=url,
                headers=headers,
                content=content,
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail="Upstream timeout") from exc
        except httpx.ConnectError as exc:
            raise HTTPException(status_code=502, detail="Upstream unreachable") from exc
