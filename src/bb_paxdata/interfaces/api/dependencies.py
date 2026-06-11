from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.config.settings import get_settings
from bb_paxdata.infrastructure.auth.rbac import check_formula_permission
from bb_paxdata.infrastructure.cache.redis import RedisCacheBackend
from bb_paxdata.infrastructure.container.service_container import ServiceContainer
from bb_paxdata.infrastructure.db.session import SessionLocal
from bb_paxdata.interfaces.http.auth.jwt_service import JWTService

security = HTTPBearer()
settings = get_settings()

_cache: RedisCacheBackend | None = None


def get_cache() -> RedisCacheBackend:
    """Retrieve the global Redis cache backend instance."""
    global _cache
    if _cache is None:
        _cache = RedisCacheBackend(url=settings.redis_url)
    return _cache


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Her istek için asenkron DB session oluşturur."""
    async with SessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()


async def get_current_reviewer(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
) -> dict[str, Any]:
    """JWT token'ı çözümler ve aktif reviewer bilgilerini döner."""
    token = credentials.credentials
    try:
        payload = JWTService.verify_access_token(token)
        return payload
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


class PermissionChecker:
    """Rol ve kapsam tabanlı erişim kontrolü sağlayan dependency sınıfı."""

    def __init__(
        self,
        required_level: str,
        scope_type: str | None = "global",
        scope_value: str | None = "global",
    ):
        self.required_level = required_level
        self.scope_type = scope_type
        self.scope_value = scope_value

    async def __call__(
        self,
        reviewer: Annotated[dict[str, Any], Depends(get_current_reviewer)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> bool:
        try:
            await check_formula_permission(
                reviewer_id=reviewer["reviewer_id"],
                required_level=self.required_level,
                scope_type=self.scope_type,
                scope_value=self.scope_value,
                session=db,
            )
            return True
        except PermissionError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


def get_service_container() -> ServiceContainer:
    """Retrieve the global ServiceContainer instance for dependency injection."""
    return ServiceContainer.get_instance()
