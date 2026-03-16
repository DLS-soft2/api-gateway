from pydantic_settings import BaseSettings


class GatewaySettings(BaseSettings):
    KEYCLOAK_ISSUER_URL: str
    KEYCLOAK_AUDIENCE: str
    USER_SERVICE_BASE_URL: str
    PROXY_TIMEOUT_SECONDS: float = 30.0

    model_config = {"env_prefix": ""}


def load_settings() -> GatewaySettings:
    return GatewaySettings()
