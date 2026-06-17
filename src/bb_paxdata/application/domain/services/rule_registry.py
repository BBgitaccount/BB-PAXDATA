import asyncio
import importlib
import importlib.util
import inspect
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from bb_paxdata.application.domain.ports.anomaly_rule import AnomalyRule

logger = structlog.get_logger(__name__)


class RuleRegistry:
    """
    Fault-tolerant ve thread-safe dinamik kural yükleyici.
    Hatalı yazılan kuralların tüm motoru çökertmesini engeller.
    """

    def __init__(self, rules_dir: str | Path | None = None):
        self.rules_dir = Path(rules_dir) if rules_dir else None
        self._rules: list[AnomalyRule] = []
        self._failed_rules: list[tuple[str, str]] = []  # (rule_file, error_message)
        self._lock = asyncio.Lock()
        self._last_reload: str = datetime.now(timezone.utc).isoformat()

    @property
    def rules(self) -> list[AnomalyRule]:
        return self._rules.copy()

    @property
    def failed_rules(self) -> list[tuple[str, str]]:
        return self._failed_rules.copy()

    @property
    def last_reload(self) -> str:
        return self._last_reload

    async def load_from_directory(self, directory: str | Path) -> None:
        async with self._lock:
            await self._load_all(Path(directory))
            self._last_reload = datetime.now(timezone.utc).isoformat()

    async def reload(self) -> None:
        if not self.rules_dir:
            raise ValueError("No rules directory configured for reload")
        await self.load_from_directory(self.rules_dir)

    async def _load_all(self, rules_path: Path) -> None:
        new_rules: list[AnomalyRule] = []
        new_failed: list[tuple[str, str]] = []

        if not rules_path.exists():
            logger.warning(f"Rules directory not found: {rules_path}")
            self._rules = []
            self._failed_rules = []
            return

        str_path = str(rules_path.absolute())
        sys_path_added = False
        if str_path not in sys.path:
            sys.path.insert(0, str_path)
            sys_path_added = True

        try:
            py_files = sorted(
                [f for f in rules_path.glob("*.py") if not f.name.startswith("__")]
            )
            for file_path in py_files:
                try:
                    module_rules = self._load_module(file_path)
                    new_rules.extend(module_rules)
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {e!s}"
                    new_failed.append((file_path.stem, error_msg))
                    logger.error(f"Failed to load rule {file_path.name}: {e}")
        finally:
            if sys_path_added:
                try:
                    sys.path.remove(str_path)
                except ValueError:
                    pass

        self._rules = new_rules
        self._failed_rules = new_failed
        logger.info(
            f"Registry reload finished: {len(new_rules)} active, {len(new_failed)} failed rules"
        )

    def _load_module(self, file_path: Path) -> list[AnomalyRule]:
        module_name = file_path.stem

        # Hot-reload: Eğer modül sistemde zaten yüklü ise sistemden silip reload ederiz
        if module_name in sys.modules:
            module = importlib.reload(sys.modules[module_name])
        else:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                raise ImportError(f"Cannot create module spec for {file_path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

        instances: list[AnomalyRule] = []
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module_name:
                continue

            # Duck typing / Protocol validasyon kontrolü
            if (
                hasattr(cls, "evaluate")
                and hasattr(cls, "rule_id")
                and hasattr(cls, "rule_name")
            ):
                try:
                    instance = cls()
                    if not instance.rule_id or not instance.rule_name:
                        continue
                    instances.append(instance)
                except Exception as e:
                    logger.error(
                        f"Failed to instantiate {name} in {file_path.name}: {e}"
                    )
        return instances

    def get_health_report(self) -> dict[str, Any]:
        return {
            "total_rules": len(self._rules) + len(self._failed_rules),
            "active_rules": len(self._rules),
            "failed_rules": self._failed_rules,
            "rule_ids": [r.rule_id for r in self._rules],
        }
