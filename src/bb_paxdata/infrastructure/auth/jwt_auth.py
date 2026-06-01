"""JWT authentication utilities for HITL dashboard."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, cast

try:
    import jwt
except ImportError:
    jwt = None


_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
_ALGORITHM = "HS256"
_TOKEN_EXPIRE_HOURS = 24


def create_jwt(
    reviewer_id: str,
    roles: list[str] | None = None,
    expires_hours: int = _TOKEN_EXPIRE_HOURS,
) -> str:
    """Create a JWT token for a reviewer (development/testing use).

    Args:
        reviewer_id: Unique reviewer identifier (e.g., email).
        roles: List of role strings (e.g., ["admin", "verdict"]).
        expires_hours: Token expiration in hours.

    Returns:
        Encoded JWT string.
    """
    if jwt is None:
        raise ImportError("PyJWT is required: pip install PyJWT")

    payload: dict[str, Any] = {
        "sub": reviewer_id,
        "roles": roles or ["verdict"],
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=expires_hours),
    }
    token = jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)
    if isinstance(token, bytes):
        return token.decode("utf-8")
    return cast(str, token)


def decode_jwt(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: Encoded JWT string.

    Returns:
        Dict with 'reviewer_id' and 'roles' keys.

    Raises:
        ValueError: If token is invalid or expired.
    """
    if jwt is None:
        raise ImportError("PyJWT is required: pip install PyJWT")

    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        return {
            "reviewer_id": payload.get("sub", "unknown"),
            "roles": payload.get("roles", []),
        }
    except jwt.ExpiredSignatureError:
        raise ValueError("JWT token has expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid JWT token: {e}")
