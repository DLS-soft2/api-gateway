from pydantic import BaseModel
from pydantic_settings import BaseSettings


class RouteConfig(BaseModel):
    prefix: str
    target_env_key: str
    strip_prefix: bool = False


class GatewaySettings(BaseSettings):
    KEYCLOAK_ISSUER_URL: str
    KEYCLOAK_AUDIENCE: str
    PROXY_TIMEOUT_SECONDS: float = 30.0

    ORDER_SERVICE_BASE_URL: str = ""
    RESTAURANT_SERVICE_BASE_URL: str = ""
    COURIER_SERVICE_BASE_URL: str = ""
    PAYMENT_SERVICE_BASE_URL: str = ""
    NOTIFICATION_SERVICE_BASE_URL: str = ""
    USER_SERVICE_BASE_URL: str = ""

    routes: list[RouteConfig] = []

    model_config = {"env_prefix": ""}


def load_settings() -> GatewaySettings:
    return GatewaySettings()
