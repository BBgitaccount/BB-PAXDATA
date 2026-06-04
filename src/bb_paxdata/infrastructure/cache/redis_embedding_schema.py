import hashlib
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class EmbeddingCacheKey:
    model_name: str
    text_hash: str

    def redis_key(self) -> str:
        return f"sbert_emb:{self.model_name}:{self.text_hash}"


class EmbeddingSerializer:
    """Binary numpy serialization for Redis efficiency."""

    DTYPE = np.float32
    HEADER_SIZE = 4  # bytes for dimension storage

    @classmethod
    def serialize(cls, vector: np.ndarray) -> bytes:
        """float32 vector -> bytes (with dimension header)."""
        assert vector.dtype == cls.DTYPE
        dim = vector.shape[0]
        dim_bytes = dim.to_bytes(cls.HEADER_SIZE, byteorder="little", signed=False)
        data_bytes = vector.tobytes()
        return dim_bytes + data_bytes

    @classmethod
    def deserialize(cls, data: bytes) -> np.ndarray:
        """bytes -> float32 vector."""
        dim = int.from_bytes(data[: cls.HEADER_SIZE], byteorder="little", signed=False)
        vector = np.frombuffer(data[cls.HEADER_SIZE :], dtype=cls.DTYPE)
        assert (
            vector.shape[0] == dim
        ), f"Dimension mismatch: expected {dim}, got {vector.shape[0]}"
        return vector.copy()

    @classmethod
    def hash_text(cls, text: str) -> str:
        """Deterministic SHA-256 hash for cache key."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]  # 32 char prefix
