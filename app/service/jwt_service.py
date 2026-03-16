import jwt
from app.models.auth import UserInfo
from app.service.jwks_service import JwksService


class JwtService:
    def __init__(self, jwks_service: JwksService, issuer: str, audience: str):
        self._jwks = jwks_service
        self._issuer = issuer
        self._audience = audience

    def verify_token(self, token: str) -> UserInfo:
        signing_key = self._jwks.get_signing_key(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=self._issuer,
            audience=self._audience,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
        return _extract_user_info(payload, self._audience)


def _extract_user_info(payload: dict, audience: str) -> UserInfo:
    roles = _extract_roles(payload, audience)
    return UserInfo(
        sub=payload["sub"],
        name=payload.get("preferred_username"),
        email=payload.get("email"),
        roles=roles,
    )


def _extract_roles(payload: dict, audience: str) -> list[str]:
    realm_roles = payload.get("realm_access", {}).get("roles", [])
    if realm_roles:
        return realm_roles
    return payload.get("resource_access", {}).get(audience, {}).get("roles", [])
