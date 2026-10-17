# backend/auth/security.py
"""
Password hashing and login-token (JWT) helpers.

- Passwords are verified against a bcrypt hash stored in .env
  (ADMIN_PASSWORD_HASH). The plain password is never stored.
- After a successful login the server issues a signed, expiring JWT.
  Every admin request must send it as:  Authorization: Bearer <token>
"""

import time
from typing import Optional

import bcrypt
import jwt

from backend.core.config import (
    ADMIN_PASSWORD_HASH,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

MIN_SECRET_LENGTH = 32
_dummy_hash: Optional[bytes] = None


# ------------------------------------------------------------
# CONFIG CHECK
# ------------------------------------------------------------

def auth_is_configured() -> bool:
    """True only if a password hash and a strong signing secret are set."""
    return bool(ADMIN_PASSWORD_HASH) and len(JWT_SECRET_KEY) >= MIN_SECRET_LENGTH


# ------------------------------------------------------------
# PASSWORDS
# ------------------------------------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # malformed hash, or password longer than bcrypt's 72-byte limit
        return False


def burn_password_check(plain: str) -> None:
    """
    Do a bcrypt check against a throwaway hash so a wrong *username*
    takes as long as a wrong *password* (prevents username probing).
    """
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = bcrypt.hashpw(b"not-the-password", bcrypt.gensalt(rounds=12))
    try:
        bcrypt.checkpw(plain.encode("utf-8"), _dummy_hash)
    except (ValueError, TypeError):
        pass


# ------------------------------------------------------------
# TOKENS
# ------------------------------------------------------------

def token_lifetime_seconds() -> int:
    return ACCESS_TOKEN_EXPIRE_MINUTES * 60


def create_access_token(subject: str) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "role": "admin",
        "iat": now,
        "exp": now + token_lifetime_seconds(),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jwt.ExpiredSignatureError / jwt.PyJWTError if invalid."""
    return jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
