"""JWT authentication and role checks (PyJWT + passlib).

Four roles: creator, reviewer and approver run the content workflow; the
brand_manager approves Constitution rules (proposal section 5.2).

Demo users live in memory so the frontend can be built before the database
is ready. When Sudiksha's users table exists, replace `_find_user` with a
database lookup; nothing else needs to change.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel

Role = Literal["creator", "reviewer", "approver", "brand_manager"]

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me-before-deploying-0001")
JWT_ALG = "HS256"
JWT_TTL_MINUTES = int(os.getenv("JWT_TTL_MINUTES", "480"))

# pbkdf2_sha256 avoids the passlib/bcrypt version warning and needs no C extension
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: Role


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


_DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demo1234")
_DEMO = [
    ("u-creator", "Aanya Rao", "creator@wordaudit.demo", "creator"),
    ("u-reviewer", "Rohan Iyer", "reviewer@wordaudit.demo", "reviewer"),
    ("u-approver", "Meera Shah", "approver@wordaudit.demo", "approver"),
    ("u-manager", "Dev Malhotra", "manager@wordaudit.demo", "brand_manager"),
]
_USERS: dict[str, tuple[UserOut, str]] = {
    email: (UserOut(id=uid, name=name, email=email, role=role), pwd_context.hash(_DEMO_PASSWORD))
    for uid, name, email, role in _DEMO
}


def _find_user(email: str) -> tuple[UserOut, str] | None:
    return _USERS.get(email.strip().lower())


def create_token(user: UserOut) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_TTL_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


_bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> UserOut:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        data = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return UserOut(id=data["sub"], name=data["name"], email=data["email"], role=data["role"])


def require_roles(*roles: Role):
    """Dependency factory: `Depends(require_roles("approver"))`."""

    def _dep(user: UserOut = Depends(current_user)) -> UserOut:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role: {', '.join(roles)}")
        return user

    return _dep


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginRequest) -> TokenOut:
    found = _find_user(body.email)
    if not found or not pwd_context.verify(body.password, found[1]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    user = found[0]
    return TokenOut(access_token=create_token(user), user=user)


@router.get("/me", response_model=UserOut)
def me(user: UserOut = Depends(current_user)) -> UserOut:
    return user
