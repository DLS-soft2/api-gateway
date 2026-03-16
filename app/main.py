from contextlib import asynccontextmanager
import os
import dotenv
from fastapi import FastAPI
from app.middleware.request_context import RequestContextMiddleware

dotenv.load_dotenv()

KEYCLOAK_ISSUER_URL = os.getenv("KEYCLOAK_ISSUER_URL", "")
KEYCLOAK_AUDIENCE = os.getenv("KEYCLOAK_AUDIENCE", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="DLS API Gateway", version="0.1.0", lifespan=lifespan)

app.add_middleware(RequestContextMiddleware)


@app.get("/healthy")
def health_check():
    return {"status": "Healthy"}


@app.get("/ready")
def readiness_check():
    return {"status": "Ready"}