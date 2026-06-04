# tests/sdk/test_watcher.py
from __future__ import annotations

import textwrap
import time

from bb_paxdata.sdk.registry import PluginRegistry
from bb_paxdata.sdk.watcher import PluginWatcher


def test_watcher_integration(tmp_path):
    registry = PluginRegistry()

    # Initially empty registry
    assert len(registry.list_plugins()) == 0

    # Start watching the temp directory
    watcher = PluginWatcher(registry, tmp_path)
    watcher.start()

    try:
        # 1. Test creation
        plugin_content = textwrap.dedent(
            """
            from pydantic import BaseModel

            class PluginMetadata(BaseModel):
                name: str
                version: str
                author: str

            class EvaluationResult(BaseModel):
                anomaly_detected: bool
                confidence: float
                anomaly_type: str | None
                explanation: str
                metadata: dict = {}

            class WatcherPlugin:
                metadata = PluginMetadata(name="WatcherPlugin", version="1.0.0", author="Tester")

                def evaluate(self, text: str, context: dict) -> EvaluationResult:
                    return EvaluationResult(
                        anomaly_detected=False,
                        confidence=0.0,
                        anomaly_type=None,
                        explanation="watcher test"
                    )
        """
        )

        plugin_file = tmp_path / "watcher_plugin.py"
        plugin_file.write_text(plugin_content, encoding="utf-8")

        # Wait for file system event propagation
        retries = 30
        loaded = False
        while retries > 0:
            plugins = registry.list_plugins()
            if len(plugins) == 1 and plugins[0].metadata.name == "WatcherPlugin":
                loaded = True
                break
            time.sleep(0.1)
            retries -= 1

        assert loaded, f"Plugin did not load. Registry: {registry.list_plugins()}"

        # 2. Test modification (update version to 1.1.0)
        modified_content = plugin_content.replace('"1.0.0"', '"1.1.0"')
        plugin_file.write_text(modified_content, encoding="utf-8")

        reloaded = False
        retries = 30
        while retries > 0:
            plugins = registry.list_plugins()
            if len(plugins) == 1 and plugins[0].metadata.version == "1.1.0":
                reloaded = True
                break
            time.sleep(0.1)
            retries -= 1

        assert (
            reloaded
        ), f"Plugin did not reload with new version. Registry: {registry.list_plugins()}"

        # 3. Test deletion
        plugin_file.unlink()

        unloaded = False
        retries = 30
        while retries > 0:
            plugins = registry.list_plugins()
            if len(plugins) == 0:
                unloaded = True
                break
            time.sleep(0.1)
            retries -= 1

        assert unloaded, f"Plugin was not unloaded. Registry: {registry.list_plugins()}"

    finally:
        watcher.stop()
