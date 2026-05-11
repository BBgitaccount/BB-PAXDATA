"""
RecoveryEngine — 6 seviyeli JSON kurtarma motoru.

AI backend'lerinden dönen ham metin yanıtlarını geçerli JSON'e dönüştürmek
için kullanılan 6 aşamalı boru hattı.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

try:
    import structlog
except ImportError:
    structlog = None


class RecoveryLevel(str, Enum):
    """JSON kurtarma seviyeleri."""

    DIRECT = "direct"  # Seviye 1
    STRIPPED = "stripped"  # Seviye 2
    FIRST_BLOCK = "first_block"  # Seviye 3
    PARTIAL = "partial"  # Seviye 4
    KEY_VALUE = "key_value"  # Seviye 5
    SCHEMA_DEFAULT = "schema_default"  # Seviye 6


@dataclass
class RecoveryResult:
    """JSON kurtarma işlemi sonucu."""

    success: bool
    data: dict[str, Any] | None
    level_used: RecoveryLevel | None = None
    error: str | None = None
    raw_input: str = ""


class RecoveryEngine:
    """
    Ham AI metin yanıtından JSON kurtarmayı dener.

    Kullanım:
        engine = RecoveryEngine()
        result = engine.recover(raw_text)
        result = engine.recover(raw_text, default_schema={"sentiment": 0.0, ...})
    """

    def __init__(self, logger: Any | None = None) -> None:
        if structlog:
            self._logger = logger or structlog.get_logger(__name__)
        else:
            # Fallback logger eğer structlog kurulu değilse
            import logging

            self._logger = logger or logging.getLogger(__name__)

    def recover(
        self,
        text: str,
        default_schema: dict[str, Any] | None = None,
    ) -> RecoveryResult:
        """
        6 seviyeyi sırayla dener.
        Her seviye deneme loglanır. Başarılı seviye info ile loglanır.
        """
        result = RecoveryResult(success=False, data=None, raw_input=text)

        # Seviye 1: Direct parse
        try:
            data = self._level_direct(text)
            if data:
                result.success = True
                result.data = data
                result.level_used = RecoveryLevel.DIRECT
                self._logger.info("recovery.success", level=RecoveryLevel.DIRECT.value)
                return result
        except Exception as exc:
            self._logger.debug(
                "recovery.attempt", level=RecoveryLevel.DIRECT.value, error=str(exc)
            )

        self._logger.debug(
            "recovery.attempt", level=RecoveryLevel.DIRECT.value, text_length=len(text)
        )

        # Seviye 2: Stripped parse
        try:
            data = self._level_stripped(text)
            if data:
                result.success = True
                result.data = data
                result.level_used = RecoveryLevel.STRIPPED
                self._logger.info(
                    "recovery.success", level=RecoveryLevel.STRIPPED.value
                )
                return result
        except Exception as exc:
            self._logger.debug(
                "recovery.attempt", level=RecoveryLevel.STRIPPED.value, error=str(exc)
            )

        self._logger.debug(
            "recovery.attempt",
            level=RecoveryLevel.STRIPPED.value,
            text_length=len(text),
        )

        # Seviye 3: First JSON block
        try:
            data = self._level_first_block(text)
            if data:
                result.success = True
                result.data = data
                result.level_used = RecoveryLevel.FIRST_BLOCK
                self._logger.info(
                    "recovery.success", level=RecoveryLevel.FIRST_BLOCK.value
                )
                return result
        except Exception as exc:
            self._logger.debug(
                "recovery.attempt",
                level=RecoveryLevel.FIRST_BLOCK.value,
                error=str(exc),
            )

        self._logger.debug(
            "recovery.attempt",
            level=RecoveryLevel.FIRST_BLOCK.value,
            text_length=len(text),
        )

        # Seviye 4: Partial / truncated JSON
        try:
            data = self._level_partial(text)
            if data:
                result.success = True
                result.data = data
                result.level_used = RecoveryLevel.PARTIAL
                self._logger.info("recovery.success", level=RecoveryLevel.PARTIAL.value)
                return result
        except Exception as exc:
            self._logger.debug(
                "recovery.attempt", level=RecoveryLevel.PARTIAL.value, error=str(exc)
            )

        self._logger.debug(
            "recovery.attempt", level=RecoveryLevel.PARTIAL.value, text_length=len(text)
        )

        # Seviye 5: Key-value regex
        try:
            data = self._level_key_value(text)
            if data:
                result.success = True
                result.data = data
                result.level_used = RecoveryLevel.KEY_VALUE
                self._logger.info(
                    "recovery.success", level=RecoveryLevel.KEY_VALUE.value
                )
                return result
        except Exception as exc:
            self._logger.debug(
                "recovery.attempt", level=RecoveryLevel.KEY_VALUE.value, error=str(exc)
            )

        self._logger.debug(
            "recovery.attempt",
            level=RecoveryLevel.KEY_VALUE.value,
            text_length=len(text),
        )

        # Seviye 6: Schema default
        try:
            data = self._level_schema_default(default_schema)
            if data:
                result.success = True
                result.data = data
                result.level_used = RecoveryLevel.SCHEMA_DEFAULT
                self._logger.info(
                    "recovery.success", level=RecoveryLevel.SCHEMA_DEFAULT.value
                )
                return result
        except Exception as exc:
            self._logger.debug(
                "recovery.attempt",
                level=RecoveryLevel.SCHEMA_DEFAULT.value,
                error=str(exc),
            )

        # Tam başarısızlık
        result.error = "All recovery levels failed"
        self._logger.warning("recovery.failed", text_preview=text[:100])

        return result

    def _level_direct(self, text: str) -> dict[str, Any] | None:
        """Seviye 1: Direct JSON parse."""
        try:
            return cast(dict[str, Any], json.loads(text))
        except (json.JSONDecodeError, TypeError):
            return None

    def _level_stripped(self, text: str) -> dict[str, Any] | None:
        """Seviye 2: Markdown bloklarını temizle ve parse et."""
        # Markdown bloklarını temizle
        cleaned = text.strip()

        # ```json ... ``` bloklarını temizle
        json_pattern = r"```(?:json)?\s*(.*?)\s*```"
        json_match = re.search(json_pattern, cleaned, re.DOTALL | re.IGNORECASE)
        if json_match:
            cleaned = json_match.group(1).strip()
        else:
            # Genel ``` ... ``` bloklarını temizle
            code_pattern = r"```\s*(.*?)\s*```"
            code_match = re.search(code_pattern, cleaned, re.DOTALL)
            if code_match:
                cleaned = code_match.group(1).strip()

        try:
            return cast(dict[str, Any], json.loads(cleaned))
        except (json.JSONDecodeError, TypeError):
            return None

    def _level_first_block(self, text: str) -> dict[str, Any] | None:
        """Seviye 3: İlk JSON bloğunu bul ve parse et."""
        # En uzun { ... } bloğunu bul
        blocks = re.findall(r"\{.*?\}", text, re.DOTALL)
        if not blocks:
            return None

        # En uzun bloğu dene
        longest_block = max(blocks, key=len)

        try:
            return cast(dict[str, Any], json.loads(longest_block))
        except (json.JSONDecodeError, TypeError):
            # Tüm blokları dene
            for block in blocks:
                try:
                    return cast(dict[str, Any], json.loads(block))
                except (json.JSONDecodeError, TypeError):
                    continue
            return None

    def _level_partial(self, text: str) -> dict[str, Any] | None:
        """Seviye 4: Kırpılmış JSON'dan anahtar-değer çiftlerini çıkar."""
        # "anahtar": değer çiftlerini bul
        pattern = r'"([^"]+)"\s*:\s*(".*?"|[\d.]+|true|false|null)'
        matches = re.findall(pattern, text, re.IGNORECASE)

        if len(matches) < 2:  # En az 2 çift olmalı
            return None

        result = {}
        for key, value in matches:
            # Değerleri doğru tiplere dönüştür
            if value.lower() in ("true", "false"):
                result[key] = value.lower() == "true"
            elif value.lower() == "null":
                result[key] = None
            elif value.startswith('"') and value.endswith('"'):
                result[key] = value[1:-1]  # String tırnaklarını kaldır
            else:
                # Sayısal değer
                try:
                    if "." in value:
                        result[key] = float(value)
                    else:
                        result[key] = int(value)
                except ValueError:
                    result[key] = value  # String olarak bırak

        return result if result else None

    def _level_key_value(self, text: str) -> dict[str, Any] | None:
        """Seviye 5: Geniş anahtar-değer örüntüleri."""
        result = {}

        # Farklı ayırıcılarla anahtar-değer çiftlerini bul
        patterns = [
            r"(\w+)\s*:\s*([^,\n]+)",  # anahtar: değer
            r"(\w+)\s*=\s*([^,\n]+)",  # anahtar = değer
            r'"([^"]+)"\s*:\s*([^,\n]+)',  # "anahtar": değer
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            for key, value in matches:
                key = key.strip()
                value = value.strip().strip("\"'")

                if key and value:
                    # Basit tip dönüşümü
                    if value.lower() in ("true", "false"):
                        result[key] = value.lower() == "true"
                    elif value.lower() == "null":
                        result[key] = None
                    else:
                        try:
                            if "." in value:
                                result[key] = float(value)
                            else:
                                result[key] = int(value)
                        except ValueError:
                            result[key] = value

        return result if result else None

    def _level_schema_default(
        self, default_schema: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Seviye 6: Varsayılan şema."""
        return default_schema
