from typing import Optional
from pydantic import BaseModel

API_KEY_TOKEN_TYPE = "api_key"  # nosec B105


class TokenInfo(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"


class UserInfo(BaseModel):
    sub: str
    name: Optional[str] = None
    email: Optional[str] = None
    roles: list[str] = []


class ProxyRequest(BaseModel):
    method: str
    path: str
    headers: dict[str, str] = {}
    body: Optional[bytes] = None
