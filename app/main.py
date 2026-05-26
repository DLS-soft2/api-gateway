from contextlib import asynccontextmanager
import dotenv
import httpx
from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.proxy import init_proxy_router
from app.api.proxy import router as proxy_router
from app.middleware.auth import init_auth_dependency
from app.middleware.request_context import RequestContextMiddleware
from app.models.settings import load_settings
from app.service.jwks_service import JwksService
from app.service.jwt_service import JwtService
from app.service.proxy_service import ProxyService

dotenv.load_dotenv()

settings = load_settings()

jwks_service = JwksService(settings.KEYCLOAK_ISSUER_URL)
jwt_service = JwtService(jwks_service, settings.KEYCLOAK_ISSUER_URL, settings.KEYCLOAK_AUDIENCE)
init_auth_dependency(jwt_service)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with httpx.AsyncClient(timeout=settings.PROXY_TIMEOUT_SECONDS) as client:
        proxy_service = ProxyService(client)
        init_proxy_router(settings, proxy_service)
        yield


app = FastAPI(title="DLS API Gateway", version="1.0.1", lifespan=lifespan)

app.add_middleware(RequestContextMiddleware)

app.include_router(health_router)
app.include_router(proxy_router)
