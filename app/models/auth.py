from typing import Optional
from pydantic import BaseModel


class UserInfo(BaseModel):
    sub: str
    name: Optional[str] = None
    email: Optional[str] = None
    roles: list[str] = []
