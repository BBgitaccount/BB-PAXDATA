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

import structlog

from bb_paxdata.infrastructure.observability.metrics import get_metrics

logger = structlog.get_logger(__name__)


class RecoveryFailureError(Exception):
    """Tüm kurtarma seviyeleri başarısız olduğunda fırlatılan exception."""

    def __init__(
        self,
        message: str,
        error_trace: list[str],
        levels_attempted: int,
        raw_input: str,
    ) -> None:
        self.message = message
        self.error_trace = error_trace
        self.levels_attempted = levels_attempted
        self.raw_input = raw_input
        super().__init__(self.message)


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
        self._logger = logger or structlog.get_logger(__name__)
        import threading

        self._lock = threading.Lock()
        self._logs: dict[str, dict[str, Any]] = {}
        self._max_log_size = 1000

    def get_recovery_log(self, data_id: str) -> dict[str, Any]:
        """data_id için kurtarma logunu döner."""
        with self._lock:
            return self._logs.get(
                data_id, {"success": False, "error": "No log found for this data_id"}
            )

    def _log_recovery(
        self,
        data_id: str | None,
        levels_attempted: int,
        result: RecoveryResult,
        error_trace: list[str],
    ) -> None:
        if data_id:
            with self._lock:
                if len(self._logs) >= self._max_log_size:
                    oldest_key = next(iter(self._logs))
                    self._logs.pop(oldest_key, None)
                self._logs[data_id] = {
                    "levels_attempted": levels_attempted,
                    "final_valid": result.success,
                    "schema_compliant": result.success,
                    "error_trace": error_trace,
                }

    def recover(
        self,
        text: str,
        default_schema: dict[str, Any] | None = None,
        data_id: str | None = None,
        raise_on_failure: bool = True,
    ) -> RecoveryResult:
        """
        6 seviyeyi sırayla dener.
        Her seviye deneme loglanır. Başarılı seviye info ile loglanır.

        Args:
            text: Kurtarılacak ham metin
            default_schema: Seviye 6 için varsayılan şema
            data_id: Loglama için veri tanımlayıcısı
            raise_on_failure: Tüm seviyeler başarısız olursa exception fırlat (varsayılan: True)

        Returns:
            RecoveryResult: Kurtarma sonucu

        Raises:
            RecoveryFailureError: Tüm seviyeler başarısız olursa ve raise_on_failure=True
        """
        result = RecoveryResult(success=False, data=None, raw_input=text)
        error_trace: list[str] = []
        levels_attempted = 0

        # Seviye 1: Direct parse
        levels_attempted += 1
        try:
            data = self._level_direct(text)
            if data is not None:
                result.success = True
                result.data = data
                result.level_used = RecoveryLevel.DIRECT
                self._logger.info("recovery.success", level=RecoveryLevel.DIRECT.value)

                # [FAZ3-METRIC]
                try:
                    get_metrics().record_json_recovery(
                        level="markdown_strip", result="success"
                    )
                except Exception:
                    pass
                self._log_recovery(data_id, levels_attempted, result, error_trace)
                return result
            else:
                error_trace.append(
                    "Level 1: Direct parse returned empty/invalid result"
                )
        except Exception as exc:
            error_trace.append(f"Level 1: {exc!s}")
            self._logger.debug(
                "recovery.attempt", level=RecoveryLevel.DIRECT.value, error=str(exc)
            )

        self._logger.debug(
            "recovery.attempt", level=RecoveryLevel.DIRECT.value, text_length=len(text)
        )

        # [FAZ3-METRIC]
        try:
            get_metrics().record_json_recovery(level="markdown_strip", result="fail")
        except Exception:
            pass

        # Seviye 2: Stripped parse
        levels_attempted += 1
        try:
            data = self._level_stripped(text)
            if data is not None:
                result.success = True
                result.data = data
                result.level_used = RecoveryLevel.STRIPPED
                self._logger.info(
                    "recovery.success", level=RecoveryLevel.STRIPPED.value
                )

                # [FAZ3-METRIC]
                try:
                    get_metrics().record_json_recovery(
                        level="think_tag", result="success"
                    )
                except Exception:
                    pass
                self._log_recovery(data_id, levels_attempted, result, error_trace)
                return result
            else:
                error_trace.append(
                    "Level 2: Stripped parse returned empty/invalid result"
                )
        except Exception as exc:
            error_trace.append(f"Level 2: {exc!s}")
            self._logger.debug(
                "recovery.attempt", level=RecoveryLevel.STRIPPED.value, error=str(exc)
            )

        self._logger.debug(
            "recovery.attempt",
            level=RecoveryLevel.STRIPPED.value,
            text_length=len(text),
        )

        # [FAZ3-METRIC]
        try:
            get_metrics().record_json_recovery(level="think_tag", result="fail")
        except Exception:
            pass

        # Seviye 3: First JSON block
        levels_attempted += 1
        try:
            data = self._level_first_block(text)
            if data is not None:
                result.success = True
                result.data = data
                result.level_used = RecoveryLevel.FIRST_BLOCK
                self._logger.info(
                    "recovery.success", level=RecoveryLevel.FIRST_BLOCK.value
                )

                # [FAZ3-METRIC]
                try:
                    get_metrics().record_json_recovery(
                        level="trailing_comma", result="success"
                    )
                except Exception:
                    pass
                self._log_recovery(data_id, levels_attempted, result, error_trace)
                return result
            else:
                error_trace.append(
                    "Level 3: First JSON block parse returned empty/invalid result"
                )
        except Exception as exc:
            error_trace.append(f"Level 3: {exc!s}")
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

        # [FAZ3-METRIC]
        try:
            get_metrics().record_json_recovery(level="trailing_comma", result="fail")
        except Exception:
            pass

        # Seviye 4: Partial / truncated JSON
        levels_attempted += 1
        try:
            data = self._level_partial(text)
            if data is not None:
                result.success = True
                result.data = data
                result.level_used = RecoveryLevel.PARTIAL
                self._logger.info("recovery.success", level=RecoveryLevel.PARTIAL.value)

                # [FAZ3-METRIC]
                try:
                    get_metrics().record_json_recovery(
                        level="single_quote", result="success"
                    )
                except Exception:
                    pass
                self._log_recovery(data_id, levels_attempted, result, error_trace)
                return result
            else:
                error_trace.append(
                    "Level 4: Partial parse returned empty/invalid result"
                )
        except Exception as exc:
            error_trace.append(f"Level 4: {exc!s}")
            self._logger.debug(
                "recovery.attempt", level=RecoveryLevel.PARTIAL.value, error=str(exc)
            )

        self._logger.debug(
            "recovery.attempt", level=RecoveryLevel.PARTIAL.value, text_length=len(text)
        )

        # [FAZ3-METRIC]
        try:
            get_metrics().record_json_recovery(level="single_quote", result="fail")
        except Exception:
            pass

        # Seviye 5: Key-value regex
        levels_attempted += 1
        try:
            data = self._level_key_value(text)
            if data is not None:
                result.success = True
                result.data = data
                result.level_used = RecoveryLevel.KEY_VALUE
                self._logger.info(
                    "recovery.success", level=RecoveryLevel.KEY_VALUE.value
                )

                # [FAZ3-METRIC]
                try:
                    get_metrics().record_json_recovery(
                        level="yaml_block", result="success"
                    )
                except Exception:
                    pass
                self._log_recovery(data_id, levels_attempted, result, error_trace)
                return result
            else:
                error_trace.append(
                    "Level 5: Key-value regex returned empty/invalid result"
                )
        except Exception as exc:
            error_trace.append(f"Level 5: {exc!s}")
            self._logger.debug(
                "recovery.attempt", level=RecoveryLevel.KEY_VALUE.value, error=str(exc)
            )

        self._logger.debug(
            "recovery.attempt",
            level=RecoveryLevel.KEY_VALUE.value,
            text_length=len(text),
        )

        # [FAZ3-METRIC]
        try:
            get_metrics().record_json_recovery(level="yaml_block", result="fail")
        except Exception:
            pass

        # Seviye 6: Schema default
        levels_attempted += 1
        try:
            data = self._level_schema_default(default_schema)
            if data is not None:
                result.success = True
                result.data = data
                result.level_used = RecoveryLevel.SCHEMA_DEFAULT
                self._logger.info(
                    "recovery.success", level=RecoveryLevel.SCHEMA_DEFAULT.value
                )

                # [FAZ3-METRIC]
                try:
                    get_metrics().record_json_recovery(
                        level="regex_salvage", result="success"
                    )
                except Exception:
                    pass
                self._log_recovery(data_id, levels_attempted, result, error_trace)
                return result
            else:
                error_trace.append(
                    "Level 6: Schema default returned empty/invalid result"
                )
        except Exception as exc:
            error_trace.append(f"Level 6: {exc!s}")
            self._logger.debug(
                "recovery.attempt",
                level=RecoveryLevel.SCHEMA_DEFAULT.value,
                error=str(exc),
            )

        # [FAZ3-METRIC]
        try:
            get_metrics().record_json_recovery(level="regex_salvage", result="fail")
        except Exception:
            pass

        # Tam başarısızlık
        result.error = "All recovery levels failed"
        self._logger.warning("recovery.failed", text_preview=text[:100])
        self._log_recovery(data_id, levels_attempted, result, error_trace)

        # Exception fırlatma (BUG-SYS-005 fix)
        if raise_on_failure:
            error_message = (
                f"All {levels_attempted} recovery levels failed for JSON recovery"
            )
            self._logger.error(
                "recovery.exception",
                error_message=error_message,
                error_trace=error_trace,
                text_preview=text[:100],
            )
            raise RecoveryFailureError(
                message=error_message,
                error_trace=error_trace,
                levels_attempted=levels_attempted,
                raw_input=text,
            )

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
        blocks: list[str] = re.findall(r"\{.*?\}", text, re.DOTALL)
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
