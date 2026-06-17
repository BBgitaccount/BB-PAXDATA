from typing import Any


def validate_json_safe(v: Any) -> None:
    """
    Recursively check if a value only contains JSON-safe primitive types.
    Allowed types: str, int, float, bool, None, list, tuple, dict (with string keys).
    """
    if v is None:
        return
    if isinstance(v, (str, int, float, bool)):
        return
    if isinstance(v, (list, tuple)):
        for val in v:
            validate_json_safe(val)
        return
    if isinstance(v, dict):
        for k, val in v.items():
            if not isinstance(k, str):
                raise TypeError(
                    f"JSON dictionary keys must be strings, got {type(k).__name__}"
                )
            validate_json_safe(val)
        return
    raise TypeError(f"Type {type(v).__name__} is not JSON safe (serializable)")
