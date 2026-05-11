"""
DiskCacheBackend — Dosya sistemi tabanlı cache implementasyonu.

Her key'i ayrı JSON dosyasına yazar. Büyük cache'lerde bellek sorunu olmaz.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from .base import CacheBackend

import structlog

logger = structlog.get_logger(__name__)

try:
    import aiofiles
    import aiofiles.os

    AIOFILES_AVAILABLE = True
except ImportError:
    aiofiles = None
    AIOFILES_AVAILABLE = False


class DiskCacheBackend(CacheBackend):
    """
    Dosya sistemi tabanlı cache.
    Her key → ayrı JSON dosyası.
    Monolitik pickle cache'in güvenli, şeffaf karşılığı.

    __init__ parametreleri:
      cache_dir: str | Path   (default: ".cache/bb_paxdata")
      max_size_mb: int        (default: 500)
    """

    def __init__(
        self,
        cache_dir: str | Path = ".cache/bb_paxdata",
        max_size_mb: int = 500,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.max_size_mb = max_size_mb

        self._logger = logger

        # Cache dizinini oluştur
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def get(self, key: str) -> Any | None:
        """Key'den değeri oku."""
        file_path = self._get_file_path(key)

        if not file_path.exists():
            return None

        try:
            content = await self._read_file(file_path)
            if content is None:
                return None

            cache_data = json.loads(content)

            # TTL kontrolü
            if cache_data.get("ttl") is not None:
                created_at = cache_data.get("created_at", 0)
                ttl = cache_data["ttl"]
                if time.time() > created_at + ttl:
                    # Süresi geçmiş, dosyayı sil
                    await self._delete_file(file_path)
                    return None

            return cache_data.get("value")

        except (json.JSONDecodeError, OSError, KeyError) as exc:
            self._logger.warning("cache.get.failed", key=key, error=str(exc))
            # Bozuk dosyayı sil
            try:
                await self._delete_file(file_path)
            except OSError:
                pass
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Değeri dosyaya yaz."""
        file_path = self._get_file_path(key)

        cache_data = {
            "key": key,
            "value": value,
            "created_at": time.time(),
            "ttl": ttl,
        }

        try:
            content = json.dumps(cache_data, ensure_ascii=False, separators=(",", ":"))
            await self._write_file(file_path, content)

            # Boyut kontrolü ve uyarı
            stats = await self.stats()
            size_mb = stats.get("size_mb", 0)
            if size_mb > self.max_size_mb:
                self._logger.warning(
                    "cache.size.warning", size_mb=size_mb, max_size_mb=self.max_size_mb
                )

        except OSError as exc:
            self._logger.warning("cache.set.failed", key=key, error=str(exc))

    async def delete(self, key: str) -> None:
        """Key'i sil."""
        file_path = self._get_file_path(key)
        await self._delete_file(file_path)

    async def exists(self, key: str) -> bool:
        """Key var mı kontrol et."""
        file_path = self._get_file_path(key)

        if not file_path.exists():
            return False

        # TTL kontrolü
        try:
            content = await self._read_file(file_path)
            if content is None:
                return False

            cache_data = json.loads(content)
            if cache_data.get("ttl") is not None:
                created_at = cache_data.get("created_at", 0)
                ttl = cache_data["ttl"]
                if time.time() > created_at + ttl:
                    await self._delete_file(file_path)
                    return False

            return True

        except (json.JSONDecodeError, OSError):
            return False

    async def clear(self, prefix: str | None = None) -> int:
        """Cache'i temizle. Prefix verilirse sadece o prefix ile başlayanları sil."""
        deleted_count = 0

        try:
            for file_path in self.cache_dir.glob("*.json"):
                if prefix:
                    try:
                        content = await self._read_file(file_path)
                        if content:
                            cache_data = json.loads(content)
                            if not cache_data.get("key", "").startswith(prefix):
                                continue
                    except (json.JSONDecodeError, OSError):
                        # Bozuk dosyayı sil
                        pass

                await self._delete_file(file_path)
                deleted_count += 1

        except OSError as exc:
            self._logger.warning("cache.clear.failed", error=str(exc))

        return deleted_count

    async def stats(self) -> dict[str, Any]:
        """Cache istatistikleri."""
        total_size = 0
        file_count = 0
        expired_count = 0
        current_time = time.time()

        try:
            for file_path in self.cache_dir.glob("*.json"):
                file_count += 1
                total_size += file_path.stat().st_size

                # TTL kontrolü
                try:
                    content = await self._read_file(file_path)
                    if content:
                        cache_data = json.loads(content)
                        if cache_data.get("ttl") is not None:
                            created_at = cache_data.get("created_at", 0)
                            ttl = cache_data["ttl"]
                            if current_time > created_at + ttl:
                                expired_count += 1
                except (json.JSONDecodeError, OSError):
                    # Bozuk dosya
                    expired_count += 1

        except OSError as exc:
            self._logger.warning("cache.stats.failed", error=str(exc))

        return {
            "file_count": file_count,
            "size_mb": round(total_size / (1024 * 1024), 2),
            "expired_count": expired_count,
            "max_size_mb": self.max_size_mb,
            "cache_dir": str(self.cache_dir),
        }

    def _get_file_path(self, key: str) -> Path:
        """Key için dosya yolunu oluştur."""
        safe_key = self.make_key(key)
        return self.cache_dir / f"{safe_key}.json"

    async def _read_file(self, file_path: Path) -> str | None:
        """Dosyayı oku (async)."""
        if AIOFILES_AVAILABLE and aiofiles is not None:
            try:
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                    return str(content) if content is not None else None
            except OSError:
                return None
        else:
            # Fallback: asyncio.to_thread ile senkron open
            def _read() -> str | None:
                try:
                    with open(file_path, encoding="utf-8") as f:
                        return f.read()
                except OSError:
                    return None

            return await asyncio.to_thread(_read)

    async def _write_file(self, file_path: Path, content: str) -> None:
        """Dosyaya yaz (async)."""
        if AIOFILES_AVAILABLE and aiofiles is not None:
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(content)
        else:
            # Fallback: asyncio.to_thread ile senkron open
            def _write() -> None:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)

            await asyncio.to_thread(_write)

    async def _delete_file(self, file_path: Path) -> None:
        """Dosyayı sil (async)."""
        try:
            # aiofiles doesn't have delete, use pathlib with asyncio.to_thread
            await asyncio.to_thread(file_path.unlink, missing_ok=True)
        except OSError:
            pass
