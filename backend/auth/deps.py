# backend/auth/deps.py
"""
FastAPI dependency that protects admin routes.

Usage (whole router):
    router = APIRouter(..., dependencies=[Depends(require_admin)])

Usage (single route):
    def handler(admin: str = Depends(require_admin)): ...
"""

from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.security import auth_is_configured, decode_access_token
from backend.core.config import ADMIN_USERNAME

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> str:
    if not auth_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin auth is not configured on the server.",
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Session expired. Please log in again.")
    except jwt.PyJWTError:
        raise _unauthorized("Invalid token")

    if payload.get("sub") != ADMIN_USERNAME or payload.get("role") != "admin":
        raise _unauthorized("Invalid token")

    return payload["sub"]
