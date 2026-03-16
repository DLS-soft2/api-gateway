from contextlib import asynccontextmanager
import dotenv
from fastapi import FastAPI
from app.middleware.auth import init_auth_dependency
from app.api.health import router as health_router
from app.middleware.request_context import RequestContextMiddleware
from app.models.settings import load_settings
from app.service.jwks_service import JwksService
from app.service.jwt_service import JwtService

dotenv.load_dotenv()

settings = load_settings()

jwks_service = JwksService(settings.KEYCLOAK_ISSUER_URL)
jwt_service = JwtService(jwks_service, settings.KEYCLOAK_ISSUER_URL, settings.KEYCLOAK_AUDIENCE)
init_auth_dependency(jwt_service)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(title="DLS API Gateway", version="0.1.0", lifespan=lifespan)

app.add_middleware(RequestContextMiddleware)

app.include_router(health_router)
