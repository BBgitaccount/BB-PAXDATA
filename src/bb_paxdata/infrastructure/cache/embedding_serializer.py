import io

import numpy as np


class EmbeddingSerializer:
    """
    Serializes numpy arrays of arbitrary shape to/from binary for Redis.
    Supports both (D,) single-vector and (T, D) token-matrix formats.
    Uses np.save/np.load to preserve shape metadata.
    """

    @staticmethod
    def serialize(array: np.ndarray) -> bytes:
        """
        Serialize numpy array to bytes while preserving shape information.

        Args:
            array: numpy array of any shape (e.g., (D,) for SBERT, (T, D) for ColBERT)

        Returns:
            Binary representation of the array with shape metadata.
        """
        buf = io.BytesIO()
        np.save(buf, array, allow_pickle=False)
        return buf.getvalue()

    @staticmethod
    def deserialize(data: bytes) -> np.ndarray:
        """
        Deserialize bytes back to numpy array with original shape.

        Args:
            data: Binary data from serialize()

        Returns:
            numpy array with original shape preserved.
        """
        buf = io.BytesIO(data)
        return np.load(buf, allow_pickle=False)
