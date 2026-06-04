# src/bb_paxdata/interfaces/http/auth/jwt_service.py
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import jwt
from bb_paxdata.config.settings import get_settings
from fastapi import HTTPException, Request, Response, status

settings = get_settings()

_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
_ALGORITHM = "HS256"

# Expiration configs (Standard secure defaults)
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Cookie and Header names
ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_COOKIE_NAME = "csrf_token"


class JWTService:
    """
    Service handling secure HttpOnly cookie-based JWT authentication,
    CSRF token protection, and refresh token rotation.
    """

    @staticmethod
    def create_tokens(reviewer_id: str, roles: list[str]) -> tuple[str, str, str]:
        """
        Generates access token, refresh token, and a CSRF token.
        """
        now = datetime.now(timezone.utc)

        # 1. Access Token (Short-lived)
        access_payload = {
            "sub": reviewer_id,
            "roles": roles,
            "iat": now,
            "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            "type": "access",
        }
        access_token = jwt.encode(access_payload, _SECRET_KEY, algorithm=_ALGORITHM)

        # 2. Refresh Token (Long-lived)
        refresh_payload = {
            "sub": reviewer_id,
            "iat": now,
            "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            "type": "refresh",
        }
        refresh_token = jwt.encode(refresh_payload, _SECRET_KEY, algorithm=_ALGORITHM)

        # 3. CSRF Token (UUID)
        csrf_token = str(uuid.uuid4())

        return access_token, refresh_token, csrf_token

    @staticmethod
    def set_auth_cookies(
        response: Response,
        access_token: str,
        refresh_token: str,
        csrf_token: str | None = None,
    ) -> None:
        """
        Set access, refresh, and CSRF tokens in cookies.
        """
        is_secure = os.getenv("ENV", "development").lower() == "production"

        response.set_cookie(
            key=ACCESS_COOKIE_NAME,
            value=access_token,
            httponly=True,
            secure=is_secure,
            samesite="strict",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        response.set_cookie(
            key=REFRESH_COOKIE_NAME,
            value=refresh_token,
            httponly=True,
            secure=is_secure,
            samesite="strict",
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        )
        if csrf_token:
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=csrf_token,
                httponly=False,  # Accessible by frontend to attach to headers
                secure=is_secure,
                samesite="strict",
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            )

    @staticmethod
    def clear_auth_cookies(response: Response) -> None:
        """
        Remove access, refresh, and CSRF cookies.
        """
        response.delete_cookie(ACCESS_COOKIE_NAME, samesite="strict")
        response.delete_cookie(REFRESH_COOKIE_NAME, samesite="strict")
        response.delete_cookie(CSRF_COOKIE_NAME, samesite="strict")

    @staticmethod
    def decode_token(token: str, expected_type: str) -> dict[str, Any]:
        """
        Decode and validate JWT token. Ensures expiration and type checks.
        """
        try:
            payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
            if payload.get("type") != expected_type:
                raise ValueError(f"Invalid token type: expected {expected_type}")
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token signature has expired")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}")

    @staticmethod
    def verify_request_auth(request: Request) -> dict[str, Any]:
        """
        Verify request credentials. Supports HttpOnly cookies and fallback to Authorization header.
        Validates CSRF token if cookie is present.
        """
        access_token = request.cookies.get(ACCESS_COOKIE_NAME)

        # Fallback to Authorization Header
        if not access_token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                access_token = auth_header.split(" ")[1]

        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials not found",
            )

        try:
            payload = JWTService.decode_token(access_token, "access")
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
            )

        # Double Submit Cookie CSRF Verification if CSRF cookie is present
        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
        if csrf_cookie:
            csrf_header = request.headers.get(CSRF_HEADER_NAME)
            if not csrf_header or csrf_header != csrf_cookie:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CSRF token validation failed",
                )

        return {
            "reviewer_id": payload.get("sub"),
            "roles": payload.get("roles", []),
        }

    @staticmethod
    def rotate_tokens(
        request: Request,
        response: Response,
        roles_loader_func: Callable[[str], list[str]],
    ) -> dict[str, Any]:
        """
        Verifies refresh token and generates a rotated set of new access and refresh tokens.
        """
        refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token missing",
            )

        try:
            payload = JWTService.decode_token(refresh_token, "refresh")
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid refresh token: {e}",
            )

        reviewer_id = payload.get("sub")
        if not reviewer_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid subject in refresh token",
            )

        # Fetch latest roles to prevent stale roles in access token
        roles = roles_loader_func(reviewer_id)

        # Generate new set
        new_access_token, new_refresh_token, new_csrf_token = JWTService.create_tokens(
            reviewer_id, roles
        )
        JWTService.set_auth_cookies(
            response, new_access_token, new_refresh_token, new_csrf_token
        )

        return {
            "status": "refreshed",
            "reviewer_id": reviewer_id,
            "roles": roles,
            "csrf_token": new_csrf_token,
        }
