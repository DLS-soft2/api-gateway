from fastapi import APIRouter, Depends, HTTPException, Request, Response
from app.middleware.auth import require_auth
from app.models.auth import UserInfo
from app.models.settings import GatewaySettings, RouteConfig
from app.service.proxy_service import ProxyService

SPOOFABLE_HEADERS = {"x-user-id", "x-user-roles", "x-user-email", "origin"}

router = APIRouter()

_settings: GatewaySettings | None = None
_proxy_service: ProxyService | None = None


def init_proxy_router(settings: GatewaySettings, proxy_service: ProxyService) -> None:
    """Wire settings and proxy service into the router module."""
    global _settings, _proxy_service  # pylint: disable=global-statement
    _settings = settings
    _proxy_service = proxy_service


def _resolve_route(path: str, routes: list[RouteConfig]) -> RouteConfig | None:
    """Return the route with the longest matching prefix, or None."""
    match: RouteConfig | None = None
    for route in routes:
        if not path.startswith(route.prefix):
            continue
        if match is None or len(route.prefix) > len(match.prefix):
            match = route
    return match


def _build_target_url(path: str, route: RouteConfig, settings: GatewaySettings) -> str:
    """Construct the full downstream URL from route config and settings."""
    base_url = getattr(settings, route.target_env_key)
    if route.rewrite_to is not None:
        forwarded_path = route.rewrite_to + path[len(route.prefix):]
    elif route.strip_prefix:
        forwarded_path = path[len(route.prefix):]
    else:
        forwarded_path = path
    return f"{base_url.rstrip('/')}{forwarded_path}"


def _build_forwarded_headers(
    request: Request,
    user: UserInfo,
) -> dict[str, str]:
    """Build headers for the upstream request, stripping spoofable and injecting trusted ones."""
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in SPOOFABLE_HEADERS and k.lower() != "host"
    }
    headers["x-user-id"] = user.sub
    headers["x-user-roles"] = ",".join(user.roles)
    headers["x-user-email"] = user.email or ""
    headers["x-request-id"] = request.state.request_id
    return headers


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_catch_all(
    request: Request,
    user: UserInfo = Depends(require_auth),
) -> Response:
    """Catch-all proxy endpoint that forwards authenticated requests to downstream services."""
    route = _resolve_route(request.url.path, _settings.routes)
    if route is None:
        raise HTTPException(status_code=404, detail="No matching route")

    target_url = _build_target_url(request.url.path, route, _settings)
    headers = _build_forwarded_headers(request, user)
    body = await request.body()

    upstream = await _proxy_service.forward(
        method=request.method,
        url=target_url,
        headers=headers,
        content=body or None,
    )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={"content-type": upstream.headers.get("content-type", "application/json")},
    )
