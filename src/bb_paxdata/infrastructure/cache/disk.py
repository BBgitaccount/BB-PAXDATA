from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import structlog

from bb_paxdata.infrastructure.observability.metrics import get_metrics

from .base import CacheBackend

logger = structlog.get_logger(__name__)

AIOFILES_AVAILABLE = False
try:
    import aiofiles as _aiofiles_check  # noqa: F401

    AIOFILES_AVAILABLE = True
except ImportError:
    pass


class DiskCacheBackend(CacheBackend):
    def __init__(
        self,
        cache_dir: str | Path = ".cache/bb_paxdata",
        max_size_mb: int = 500,
    ) -> None:
        self._cache_dir = Path(cache_dir)
        self._max_size_mb = max_size_mb
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    async def _read_file(self, path: Path) -> Any:
        """aiofiles varsa async, yoksa asyncio.to_thread ile oku."""
        if not path.exists():
            return None
        if AIOFILES_AVAILABLE:
            import aiofiles

            async with aiofiles.open(path, encoding="utf-8") as f:
                content = await f.read()
                return str(content) if content is not None else None
        content = await asyncio.to_thread(path.read_text, encoding="utf-8")
        return content

    async def _write_file(self, path: Path, content: str) -> None:
        """aiofiles varsa async, yoksa asyncio.to_thread ile yaz."""
        if AIOFILES_AVAILABLE:
            import aiofiles

            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(content)
        else:
            await asyncio.to_thread(path.write_text, content, encoding="utf-8")

    async def get(self, key: str) -> Any | None:
        path = self._cache_dir / f"{self.make_key(key)}.json"
        try:
            raw = await self._read_file(path)
            if raw is None:
                # [FAZ3-METRIC]
                try:
                    get_metrics().record_cache_operation(
                        cache_type="disk", operation="get", result="miss"
                    )
                except Exception:
                    pass
                return None
            record: dict[str, Any] = json.loads(raw)
            # TTL kontrolü
            import time

            ttl = record.get("ttl")
            if ttl is not None:
                created_at = record.get("created_at", 0.0)
                if time.time() > created_at + ttl:
                    await self.delete(key)
                    # [FAZ3-METRIC]
                    try:
                        get_metrics().record_cache_operation(
                            cache_type="disk", operation="get", result="miss"
                        )
                    except Exception:
                        pass
                    return None

            # [FAZ3-METRIC]
            try:
                get_metrics().record_cache_operation(
                    cache_type="disk", operation="get", result="hit"
                )
            except Exception:
                pass
            return record.get("value")
        except Exception as exc:
            logger.warning("disk_cache.get.failed", key=key, error=str(exc))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        import time

        path = self._cache_dir / f"{self.make_key(key)}.json"
        record = {
            "key": key,
            "value": value,
            "created_at": time.time(),
            "ttl": ttl,
        }
        try:
            await self._write_file(path, json.dumps(record, ensure_ascii=False))
            # [FAZ3-METRIC]
            try:
                get_metrics().record_cache_operation(
                    cache_type="disk", operation="set", result="hit"
                )
            except Exception:
                pass
        except Exception as exc:
            logger.warning("disk_cache.set.failed", key=key, error=str(exc))

    async def delete(self, key: str) -> None:
        path = self._cache_dir / f"{self.make_key(key)}.json"
        await asyncio.to_thread(lambda: path.unlink(missing_ok=True))

    async def exists(self, key: str) -> bool:
        path = self._cache_dir / f"{self.make_key(key)}.json"
        return path.exists()

    async def clear(self, prefix: str | None = None) -> int:
        deleted = 0
        for file in self._cache_dir.glob("*.json"):
            if prefix is None or file.stem.startswith(prefix):
                file.unlink(missing_ok=True)
                deleted += 1
        return deleted

    async def stats(self) -> dict[str, Any]:
        files = list(self._cache_dir.glob("*.json"))
        total_bytes = sum(f.stat().st_size for f in files if f.exists())
        return {
            "backend": "disk",
            "total_keys": len(files),
            "size_mb": round(total_bytes / 1024 / 1024, 2),
            "cache_dir": str(self._cache_dir),
        }
