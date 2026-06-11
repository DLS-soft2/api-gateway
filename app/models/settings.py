from pydantic import BaseModel
from pydantic_settings import BaseSettings


class RouteConfig(BaseModel):
    prefix: str
    target_env_key: str
    strip_prefix: bool = False
    rewrite_to: str | None = None


class GatewaySettings(BaseSettings):
    KEYCLOAK_ISSUER_URL: str
    KEYCLOAK_JWKS_ISSUER_URL: str = ""
    KEYCLOAK_AUDIENCE: str
    PROXY_TIMEOUT_SECONDS: float = 30.0

    ORDER_SERVICE_BASE_URL: str = ""
    RESTAURANT_SERVICE_BASE_URL: str = ""
    COURIER_SERVICE_BASE_URL: str = ""
    PAYMENT_SERVICE_BASE_URL: str = ""
    NOTIFICATION_SERVICE_BASE_URL: str = ""
    USER_SERVICE_BASE_URL: str = ""

    routes: list[RouteConfig] = [
        RouteConfig(prefix="/api/v1/orders", target_env_key="ORDER_SERVICE_BASE_URL"),
        RouteConfig(prefix="/api/v2/restaurants", target_env_key="RESTAURANT_SERVICE_BASE_URL"),
        RouteConfig(prefix="/api/v2/couriers", target_env_key="COURIER_SERVICE_BASE_URL"),
        RouteConfig(prefix="/api/v2/deliveries", target_env_key="COURIER_SERVICE_BASE_URL"),
        RouteConfig(prefix="/api/v1/payments", target_env_key="PAYMENT_SERVICE_BASE_URL"),
        RouteConfig(prefix="/api/v1/notifications", target_env_key="NOTIFICATION_SERVICE_BASE_URL"),
        RouteConfig(prefix="/api/v1/users", target_env_key="USER_SERVICE_BASE_URL"),
        RouteConfig(
            prefix="/restaurant-graphql",
            target_env_key="RESTAURANT_SERVICE_BASE_URL",
            rewrite_to="/graphql",
        ),
        RouteConfig(prefix="/graphql", target_env_key="USER_SERVICE_BASE_URL"),
    ]

    model_config = {"env_prefix": ""}


def load_settings() -> GatewaySettings:
    return GatewaySettings()
