"""JWT login and role checks for the website (/api routes).

Demo users live in memory so the deployed demo works without a users table.
Swap `find_user` for a database lookup when real accounts are needed.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel

Role = Literal["creator", "reviewer", "approver", "brand_manager"]

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me-before-deploying-0001")
JWT_ALG = "HS256"
JWT_TTL_MINUTES = int(os.getenv("JWT_TTL_MINUTES", "480"))

_pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: Role


DEMO_USERS = [
    UserOut(id="u-creator", name="Aanya Rao", email="creator@wordaudit.demo", role="creator"),
    UserOut(id="u-reviewer", name="Rohan Iyer", email="reviewer@wordaudit.demo", role="reviewer"),
    UserOut(id="u-approver", name="Meera Shah", email="approver@wordaudit.demo", role="approver"),
    UserOut(id="u-manager", name="Dev Malhotra", email="manager@wordaudit.demo", role="brand_manager"),
]
_HASH = _pwd.hash(os.getenv("DEMO_PASSWORD", "demo1234"))
_BY_EMAIL = {u.email: u for u in DEMO_USERS}
_BY_NAME = {u.name: u for u in DEMO_USERS}


def find_user(email: str) -> Optional[UserOut]:
    return _BY_EMAIL.get(email.strip().lower())


def user_by_name(name: str) -> Optional[UserOut]:
    """Content stores the creator's display name; map it back to a user id."""
    return _BY_NAME.get(name)


def check_password(password: str) -> bool:
    return _pwd.verify(password, _HASH)


def create_token(user: UserOut) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user.id, "email": user.email, "name": user.name, "role": user.role,
               "iat": now, "exp": now + timedelta(minutes=JWT_TTL_MINUTES)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


_bearer = HTTPBearer(auto_error=False)


def current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> UserOut:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in")
    try:
        data = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has expired. Please sign in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in")
    return UserOut(id=data["sub"], name=data["name"], email=data["email"], role=data["role"])


def require_roles(*roles: str):
    def dep(user: UserOut = Depends(current_user)) -> UserOut:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Only {' or '.join(roles)} can do this")
        return user

    return dep
