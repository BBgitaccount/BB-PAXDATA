"""
CacheBackend — Backend-agnostik async cache arayüzü.

Tüm cache implementasyonları bu soyut sınıfı uygular.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from typing import Any


class CacheBackend(ABC):
    """
    Backend-agnostik async cache arayüzü.
    Tüm implementasyonlar bu sınıfı uygular.
    """

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Key bulunamazsa None döner."""

    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,  # saniye cinsinden, None = sonsuz
    ) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def clear(self, prefix: str | None = None) -> int:
        """Silinen key sayısını döner."""

    @abstractmethod
    async def stats(self) -> dict[str, Any]:
        """hit/miss oranı, toplam key sayısı, boyut vb."""

    def make_key(self, *parts: str) -> str:
        """
        Deterministik cache anahtarı üretir.
        sha256(:join(parts))[:16]
        Monolitik get_cache_key() mantığının karşılığı.
        """
        combined = ":".join(parts)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
