import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.models.auth import UserInfo
from app.service.jwt_service import JwtService

_bearer_scheme = HTTPBearer(auto_error=False)

_jwt_service: JwtService | None = None


def init_auth_dependency(jwt_service: JwtService) -> None:
    global _jwt_service  # pylint: disable=global-statement
    _jwt_service = jwt_service


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> UserInfo:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = credentials.credentials
    try:
        user_info = _jwt_service.verify_token(token)
    except jwt.InvalidIssuerError as exc:
        raise HTTPException(status_code=401, detail="Invalid issuer") from exc
    except jwt.InvalidAudienceError as exc:
        raise HTTPException(status_code=401, detail="Invalid audience") from exc
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except (jwt.InvalidTokenError, jwt.PyJWKClientError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    request.state.user_info = user_info
    return user_info
