"""JWT authentication utilities for HITL dashboard.

DEPRECATED: This module is deprecated. Use bb_paxdata.interfaces.http.auth.jwt_service.JWTService instead.
The new JWTService provides:
- Short-lived access tokens (15 minutes) for better security
- Long-lived refresh tokens (7 days) with rotation
- CSRF protection via double-submit cookie pattern
- HttpOnly cookie support

This module will be removed in a future version.
"""

from __future__ import annotations

import warnings
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    import jwt
except ImportError:
    jwt = None


from bb_paxdata.config.settings import get_settings

_SECRET_KEY = get_settings().jwt_secret_key
_ALGORITHM = "HS256"
_TOKEN_EXPIRE_HOURS = 24


def create_jwt(
    reviewer_id: str,
    roles: list[str] | None = None,
    expires_hours: int = _TOKEN_EXPIRE_HOURS,
) -> str:
    """Create a JWT token for a reviewer (development/testing use).

    DEPRECATED: Use JWTService.create_tokens() instead.

    Args:
        reviewer_id: Unique reviewer identifier (e.g., email).
        roles: List of role strings (e.g., ["admin", "verdict"]).
        expires_hours: Token expiration in hours.

    Returns:
        Encoded JWT string.
    """
    warnings.warn(
        "create_jwt is deprecated. Use JWTService.create_tokens() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    if jwt is None:
        raise ImportError("PyJWT is required: pip install PyJWT")

    payload: dict[str, Any] = {
        "sub": reviewer_id,
        "roles": roles or ["verdict"],
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=expires_hours),
    }
    token = jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)
    if isinstance(token, bytes):
        return token.decode("utf-8")
    return token


def decode_jwt(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    DEPRECATED: Use JWTService.verify_access_token() instead.

    Args:
        token: Encoded JWT string.

    Returns:
        Dict with 'reviewer_id' and 'roles' keys.

    Raises:
        ValueError: If token is invalid or expired.
    """
    warnings.warn(
        "decode_jwt is deprecated. Use JWTService.verify_access_token() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
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
