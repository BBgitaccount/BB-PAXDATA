# src/bb_paxdata/infrastructure/scheduled_reports/embed_token.py
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

import jwt

from bb_paxdata.config.settings import get_settings

settings = get_settings()


class EmbedTokenManager:
    """JWT-based embed token management for iframe security."""

    def __init__(self):
        self.secret_key = getattr(
            settings, "embed_secret_key", secrets.token_urlsafe(32)
        )

    def create_embed_token(
        self,
        scheduled_report_id: str,
        name: str,
        allowed_origins: list[str],
        expires_in_days: int | None = None,
    ) -> str:
        """
        Create a JWT embed token for iframe access.

        Args:
            scheduled_report_id: ID of the scheduled report
            name: Token name (e.g., "Dashboard Embed")
            allowed_origins: List of allowed origins for CSP
            expires_in_days: Token expiration in days (None = no expiration)

        Returns:
            JWT token string
        """
        payload = {
            "sub": scheduled_report_id,
            "type": "embed",
            "name": name,
            "origins": allowed_origins,
            "iat": datetime.utcnow(),
        }

        if expires_in_days:
            payload["exp"] = datetime.utcnow() + timedelta(days=expires_in_days)

        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def verify_embed_token(self, token: str, request_origin: str) -> dict:
        """
        Verify JWT embed token and check origin.

        Args:
            token: JWT token string
            request_origin: Origin of the request

        Returns:
            Decoded payload

        Raises:
            jwt.InvalidTokenError: Token is invalid
            EmbedOriginNotAllowedError: Origin not in allowed list
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise jwt.InvalidTokenError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(f"Invalid token: {e}")

        # Check origin if specified
        allowed_origins = payload.get("origins", [])
        if allowed_origins and request_origin not in allowed_origins:
            raise EmbedOriginNotAllowedError(
                f"Origin '{request_origin}' not in allowed origins: {allowed_origins}"
            )

        return payload


class EmbedOriginNotAllowedError(Exception):
    """Raised when embed token origin is not allowed."""

    pass
