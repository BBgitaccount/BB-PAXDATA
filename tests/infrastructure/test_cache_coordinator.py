"""
CacheCoordinator testleri - BUG-SYS-011 çözümü.

Redis ve Disk cache arasındaki invalidation tutarlılığını test eder.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bb_paxdata.infrastructure.cache.base import CacheBackend
from bb_paxdata.infrastructure.cache.cache_coordinator import CacheCoordinator
from bb_paxdata.infrastructure.cache.disk import DiskCacheBackend


class MockCacheBackend(CacheBackend):
    """Test için mock cache backend."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._deleted_keys: list[str] = []
        self._cleared_prefixes: list[str | None] = []

    async def get(self, key: str) -> Any | None:
        return self._data.get(key)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        self._data[key] = value

    async def delete(self, key: str) -> None:
        self._deleted_keys.append(key)
        if key in self._data:
            del self._data[key]

    async def exists(self, key: str) -> bool:
        return key in self._data

    async def clear(self, prefix: str | None = None) -> int:
        self._cleared_prefixes.append(prefix)
        if prefix is None:
            count = len(self._data)
            self._data.clear()
            return count
        count = 0
        keys_to_delete = [k for k in self._data if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._data[k]
            count += 1
        return count

    async def stats(self) -> dict[str, Any]:
        return {"backend": "mock", "total_keys": len(self._data)}


class TestCacheCoordinator:
    """CacheCoordinator testleri."""

    @pytest.mark.asyncio
    async def test_coordinator_basic_operations(self) -> None:
        """Temel cache işlemlerini test et."""
        primary = MockCacheBackend()
        secondary = MockCacheBackend()
        coordinator = CacheCoordinator(
            primary_backend=primary,
            secondary_backends=[secondary],
            enable_pubsub=False,
        )

        # Set operation
        await coordinator.set("test_key", {"data": "value"})
        assert await primary.get("test_key") == {"data": "value"}
        assert await secondary.get("test_key") == {"data": "value"}

        # Get operation
        result = await coordinator.get("test_key")
        assert result == {"data": "value"}

        # Exists operation
        assert await coordinator.exists("test_key") is True
        assert await coordinator.exists("nonexistent") is False

        await coordinator.close()

    @pytest.mark.asyncio
    async def test_delete_propagates_to_secondaries(self) -> None:
        """Delete işleminin tüm backend'lere yayılmasını test et."""
        primary = MockCacheBackend()
        secondary = MockCacheBackend()
        coordinator = CacheCoordinator(
            primary_backend=primary,
            secondary_backends=[secondary],
            enable_pubsub=False,
        )

        # Set data
        await coordinator.set("test_key", {"data": "value"})
        assert await primary.exists("test_key") is True
        assert await secondary.exists("test_key") is True

        # Delete
        await coordinator.delete("test_key")

        # Verify deletion in all backends
        assert await primary.exists("test_key") is False
        assert await secondary.exists("test_key") is False
        assert "test_key" in primary._deleted_keys
        assert "test_key" in secondary._deleted_keys

        await coordinator.close()

    @pytest.mark.asyncio
    async def test_clear_propagates_to_secondaries(self) -> None:
        """Clear işleminin tüm backend'lere yayılmasını test et."""
        primary = MockCacheBackend()
        secondary = MockCacheBackend()
        coordinator = CacheCoordinator(
            primary_backend=primary,
            secondary_backends=[secondary],
            enable_pubsub=False,
        )

        # Set multiple keys
        await coordinator.set("prefix:key1", {"data": "value1"})
        await coordinator.set("prefix:key2", {"data": "value2"})
        await coordinator.set("other:key", {"data": "value3"})

        # Clear with prefix
        deleted = await coordinator.clear(prefix="prefix:")

        # Verify clear in all backends
        assert deleted == 2
        assert await primary.exists("prefix:key1") is False
        assert await primary.exists("prefix:key2") is False
        assert await primary.exists("other:key") is True
        assert await secondary.exists("prefix:key1") is False
        assert await secondary.exists("prefix:key2") is False
        assert await secondary.exists("other:key") is True
        assert "prefix:" in primary._cleared_prefixes
        assert "prefix:" in secondary._cleared_prefixes

        await coordinator.close()

    @pytest.mark.asyncio
    async def test_clear_without_prefix(self) -> None:
        """Prefix olmadan clear işlemini test et."""
        primary = MockCacheBackend()
        secondary = MockCacheBackend()
        coordinator = CacheCoordinator(
            primary_backend=primary,
            secondary_backends=[secondary],
            enable_pubsub=False,
        )

        # Set data
        await coordinator.set("key1", {"data": "value1"})
        await coordinator.set("key2", {"data": "value2"})

        # Clear all
        deleted = await coordinator.clear()

        # Verify all cleared
        assert deleted == 2
        assert await primary.exists("key1") is False
        assert await primary.exists("key2") is False
        assert await secondary.exists("key1") is False
        assert await secondary.exists("key2") is False
        assert None in primary._cleared_prefixes
        assert None in secondary._cleared_prefixes

        await coordinator.close()

    @pytest.mark.asyncio
    async def test_secondary_failure_doesnt_affect_primary(self) -> None:
        """Secondary backend hatası primary'i etkilememeli."""
        primary = MockCacheBackend()

        class FailingBackend(CacheBackend):
            def __init__(self) -> None:
                self._data: dict[str, Any] = {}

            async def get(self, key: str) -> Any | None:
                return self._data.get(key)

            async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
                raise RuntimeError("Secondary backend failed")

            async def delete(self, key: str) -> None:
                raise RuntimeError("Secondary backend failed")

            async def exists(self, key: str) -> bool:
                return key in self._data

            async def clear(self, prefix: str | None = None) -> int:
                raise RuntimeError("Secondary backend failed")

            async def stats(self) -> dict[str, Any]:
                return {"backend": "failing"}

        failing_secondary = FailingBackend()
        coordinator = CacheCoordinator(
            primary_backend=primary,
            secondary_backends=[failing_secondary],
            enable_pubsub=False,
        )

        # Set should succeed despite secondary failure
        await coordinator.set("test_key", {"data": "value"})
        assert await primary.get("test_key") == {"data": "value"}

        # Delete should succeed despite secondary failure
        await coordinator.delete("test_key")
        assert await primary.exists("test_key") is False

        await coordinator.close()

    @pytest.mark.asyncio
    async def test_make_key_delegates_to_primary(self) -> None:
        """make_key metodunun primary'e delege olduğunu test et."""
        primary = MockCacheBackend()
        coordinator = CacheCoordinator(
            primary_backend=primary,
            secondary_backends=[],
            enable_pubsub=False,
        )

        key = coordinator.make_key("prefix", "subkey", "value")
        assert key == primary.make_key("prefix", "subkey", "value")

        await coordinator.close()

    @pytest.mark.asyncio
    async def test_stats_delegates_to_primary(self) -> None:
        """stats metodunun primary'e delege olduğunu test et."""
        primary = MockCacheBackend()
        coordinator = CacheCoordinator(
            primary_backend=primary,
            secondary_backends=[],
            enable_pubsub=False,
        )

        await coordinator.set("key1", {"data": "value1"})
        await coordinator.set("key2", {"data": "value2"})

        stats = await coordinator.stats()
        assert stats["total_keys"] == 2
        assert stats["backend"] == "mock"

        await coordinator.close()

    @pytest.mark.asyncio
    async def test_coordinator_with_disk_cache(self) -> None:
        """CacheCoordinator'ı DiskCacheBackend ile test et."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            primary = DiskCacheBackend(cache_dir=Path(tmpdir) / "primary")
            secondary = DiskCacheBackend(cache_dir=Path(tmpdir) / "secondary")
            coordinator = CacheCoordinator(
                primary_backend=primary,
                secondary_backends=[secondary],
                enable_pubsub=False,
            )

            # Set data
            await coordinator.set("test_key", {"data": "value"})
            assert await coordinator.get("test_key") == {"data": "value"}

            # Verify in both backends
            assert await primary.get("test_key") == {"data": "value"}
            assert await secondary.get("test_key") == {"data": "value"}

            # Delete
            await coordinator.delete("test_key")
            assert await coordinator.get("test_key") is None
            assert await primary.get("test_key") is None
            assert await secondary.get("test_key") is None

            await coordinator.close()

    @pytest.mark.asyncio
    async def test_multiple_secondaries(self) -> None:
        """Birden fazla secondary backend ile test et."""
        primary = MockCacheBackend()
        secondary1 = MockCacheBackend()
        secondary2 = MockCacheBackend()
        coordinator = CacheCoordinator(
            primary_backend=primary,
            secondary_backends=[secondary1, secondary2],
            enable_pubsub=False,
        )

        # Set
        await coordinator.set("test_key", {"data": "value"})
        assert await primary.get("test_key") == {"data": "value"}
        assert await secondary1.get("test_key") == {"data": "value"}
        assert await secondary2.get("test_key") == {"data": "value"}

        # Delete
        await coordinator.delete("test_key")
        assert await primary.exists("test_key") is False
        assert await secondary1.exists("test_key") is False
        assert await secondary2.exists("test_key") is False

        await coordinator.close()

    @pytest.mark.asyncio
    async def test_empty_secondaries(self) -> None:
        """Secondary backend olmadan çalışmayı test et."""
        primary = MockCacheBackend()
        coordinator = CacheCoordinator(
            primary_backend=primary,
            secondary_backends=[],
            enable_pubsub=False,
        )

        # Should work like a passthrough
        await coordinator.set("test_key", {"data": "value"})
        assert await coordinator.get("test_key") == {"data": "value"}
        await coordinator.delete("test_key")
        assert await coordinator.exists("test_key") is False

        await coordinator.close()

    @pytest.mark.asyncio
    async def test_pubsub_disabled_by_default(self) -> None:
        """Pub/sub kapalıyken çalışmayı test et."""
        primary = MockCacheBackend()
        coordinator = CacheCoordinator(
            primary_backend=primary,
            secondary_backends=[],
            enable_pubsub=False,
        )

        # Operations should work without pub/sub
        await coordinator.set("test_key", {"data": "value"})
        assert await coordinator.get("test_key") == {"data": "value"}
        await coordinator.delete("test_key")

        # Listener should not be running
        assert coordinator._pubsub_listener_running is False

        await coordinator.close()
