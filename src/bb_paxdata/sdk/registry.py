# src/bb_paxdata/sdk/registry.py
from __future__ import annotations

import pathlib
import threading
from dataclasses import dataclass, field

import structlog
from bb_paxdata.sdk.protocols import PluginMetadata
from bb_paxdata.sdk.sandbox import SandboxResult, run_plugin_in_sandbox

logger = structlog.get_logger(__name__)


@dataclass
class PluginEntry:
    path: pathlib.Path
    metadata: PluginMetadata
    enabled: bool = True
    load_errors: list[str] = field(default_factory=list)


class PluginRegistry:
    """
    Thread-safe plugin kayıt ve yönetim sistemi.
    Birden fazla worker thread eş zamanlı olarak registry'ye erişebilir.
    """

    def __init__(self) -> None:
        self._lock = (
            threading.RLock()
        )  # Reentrant lock (aynı thread içinde nested lock)
        self._plugins: dict[str, PluginEntry] = {}

    def register(self, path: pathlib.Path) -> PluginEntry | None:
        """
        Plugin dosyasını kayıt eder. Metadata doğrulaması yapar.
        Hata durumunda kayıt etmez, None döner.
        """
        if not path.exists() or not path.suffix == ".py":
            logger.error("Invalid plugin path: %s", path)
            return None

        # Metadata çıkarma için sandbox kullan
        metadata_result = self._extract_metadata(path)
        if not metadata_result:
            return None

        entry = PluginEntry(path=path, metadata=metadata_result)
        with self._lock:
            self._plugins[metadata_result.name] = entry
            logger.info(
                "Plugin registered: %s v%s",
                metadata_result.name,
                metadata_result.version,
            )
        return entry

    def unregister(self, plugin_name: str) -> bool:
        with self._lock:
            if plugin_name in self._plugins:
                del self._plugins[plugin_name]
                logger.info("Plugin unregistered: %s", plugin_name)
                return True
        return False

    def evaluate_all(self, text: str, context: dict) -> dict[str, SandboxResult]:
        """Tüm aktif plugin'leri paralel olarak çalıştırır."""
        with self._lock:
            active = {
                name: entry for name, entry in self._plugins.items() if entry.enabled
            }

        results: dict[str, SandboxResult] = {}
        # ThreadPoolExecutor ile paralel sandbox execution
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=min(4, len(active))) as executor:
            future_to_name = {
                executor.submit(run_plugin_in_sandbox, entry.path, text, context): name
                for name, entry in active.items()
            }
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    results[name] = future.result()
                except Exception as exc:
                    results[name] = SandboxResult(
                        success=False, result=None, error=str(exc)
                    )

        return results

    def list_plugins(self) -> list[PluginEntry]:
        with self._lock:
            return list(self._plugins.values())

    def _extract_metadata(self, path: pathlib.Path) -> PluginMetadata | None:
        """Sandbox içinde plugin metadata'sını çeker."""
        import json
        import subprocess
        import sys
        import textwrap

        bootstrap = textwrap.dedent(
            f"""
            import importlib.util, json, pathlib
            path = pathlib.Path({str(path)!r})
            spec = importlib.util.spec_from_file_location("p", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for name in dir(mod):
                obj = getattr(mod, name)
                if isinstance(obj, type) and hasattr(obj, 'metadata') and hasattr(obj, 'evaluate'):
                    m = obj.metadata if isinstance(obj.metadata, dict) else obj().metadata.model_dump()
                    print(json.dumps(m))
                    break
        """
        )
        try:
            proc = subprocess.run(
                [sys.executable, "-c", bootstrap],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return PluginMetadata(**json.loads(proc.stdout.strip()))
        except Exception as exc:
            logger.error("Metadata extraction failed for %s: %s", path, exc)
        return None
