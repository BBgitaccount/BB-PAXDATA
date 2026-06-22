"""
Cache backend implementations.

Backend-agnostik cache arayüzü ve çeşitli implementasyonları.
"""

from .base import CacheBackend
from .cache_coordinator import CacheCoordinator
from .disk import DiskCacheBackend

# Redis opsiyonel — kurulu değilse import hatası vermemeli
try:
    from .redis import RedisCacheBackend

    __all__ = [
        "CacheBackend",
        "CacheCoordinator",
        "DiskCacheBackend",
        "RedisCacheBackend",
    ]
except ImportError:
    __all__ = ["CacheBackend", "CacheCoordinator", "DiskCacheBackend"]
