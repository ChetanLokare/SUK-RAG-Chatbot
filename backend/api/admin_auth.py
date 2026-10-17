# backend/api/admin_auth.py

import secrets
import time
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from backend.auth.deps import require_admin
from backend.auth.security import (
    auth_is_configured,
    burn_password_check,
    create_access_token,
    token_lifetime_seconds,
    verify_password,
)
from backend.core.config import (
    ADMIN_PASSWORD_HASH,
    ADMIN_USERNAME,
    LOGIN_LOCKOUT_SECONDS,
    LOGIN_MAX_FAILURES,
)

router = APIRouter(prefix="/admin/auth", tags=["Admin Auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


# ------------------------------------------------------------
# Simple in-memory brute-force limiter (per client IP).
# Resets on server restart and is per-process, which is fine
# for a single uvicorn instance.
# ------------------------------------------------------------

_failures: Dict[str, List[float]] = {}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _recent_failures(ip: str) -> List[float]:
    cutoff = time.time() - LOGIN_LOCKOUT_SECONDS
    recent = [t for t in _failures.get(ip, []) if t > cutoff]
    if recent:
        _failures[ip] = recent
    else:
        _failures.pop(ip, None)
    return recent


@router.post("/login")
def admin_login(payload: LoginRequest, request: Request):

    if not auth_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin auth is not configured on the server.",
        )

    ip = _client_ip(request)

    if len(_recent_failures(ip)) >= LOGIN_MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again in a few minutes.",
        )

    username_ok = secrets.compare_digest(
        payload.username.encode("utf-8"),
        ADMIN_USERNAME.encode("utf-8"),
    )

    if username_ok:
        password_ok = verify_password(payload.password, ADMIN_PASSWORD_HASH)
    else:
        burn_password_check(payload.password)
        password_ok = False

    if not (username_ok and password_ok):
        _failures.setdefault(ip, []).append(time.time())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    _failures.pop(ip, None)

    return {
        "success": True,
        "token": create_access_token(ADMIN_USERNAME),
        "token_type": "bearer",
        "expires_in": token_lifetime_seconds(),
    }


@router.get("/me")
def admin_me(admin: str = Depends(require_admin)):
    """Lets the frontend check that its stored token is still valid."""
    return {"username": admin}
