from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from bb_paxdata.config.settings import get_settings
from bb_paxdata.infrastructure.cache.redis import RedisCacheBackend
from bb_paxdata.infrastructure.container.service_container import ServiceContainer
from bb_paxdata.infrastructure.db.session import SessionLocal

security = HTTPBearer(auto_error=False)
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
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict[str, Any]:
    """
    JWT token'ı çözümler ve aktif reviewer bilgilerini dönderir.
    DISABLED: Authentication devre dışı bırakıldı, her zaman admin döner.
    """
    # Authentication disabled - always return admin user
    return {
        "reviewer_id": "admin",
        "roles": ["admin"],
        "scope_type": "global",
        "scope_value": "*",
    }


class PermissionChecker:
    """Rol ve kapsam tabanlı erişim kontrolü sağlayan dependency sınıfı.
    DISABLED: Permission check devre dışı bırakıldı, her zaman True döner.
    """

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
        # Permission check disabled - always return True
        return True


def get_service_container() -> ServiceContainer:
    """Retrieve the global ServiceContainer instance for dependency injection."""
    return ServiceContainer.get_instance()
