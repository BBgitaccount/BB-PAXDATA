# tests/sdk/test_sandbox.py
from __future__ import annotations

import textwrap

from bb_paxdata.sdk.sandbox import run_plugin_in_sandbox


def test_sandbox_success(tmp_path):
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

        class TestPlugin:
            metadata = PluginMetadata(name="TestPlugin", version="1.0.0", author="Tester")

            def evaluate(self, text: str, context: dict) -> EvaluationResult:
                return EvaluationResult(
                    anomaly_detected=True,
                    confidence=0.85,
                    anomaly_type="test_anomaly",
                    explanation=f"Processed text: {text}",
                    metadata={"context_key": context.get("key")}
                )
    """
    )
    plugin_file = tmp_path / "test_plugin.py"
    plugin_file.write_text(plugin_content, encoding="utf-8")

    res = run_plugin_in_sandbox(plugin_file, "hello world", {"key": "value"})

    assert res.success is True
    assert res.error is None
    assert res.result is not None
    assert res.result["anomaly_detected"] is True
    assert res.result["confidence"] == 0.85
    assert res.result["anomaly_type"] == "test_anomaly"
    assert res.result["explanation"] == "Processed text: hello world"
    assert res.result["metadata"]["context_key"] == "value"


def test_sandbox_crash(tmp_path):
    plugin_content = textwrap.dedent(
        """
        from pydantic import BaseModel

        class PluginMetadata(BaseModel):
            name: str
            version: str
            author: str

        class TestPlugin:
            metadata = PluginMetadata(name="CrashPlugin", version="1.0.0", author="Tester")

            def evaluate(self, text: str, context: dict):
                raise ZeroDivisionError("Simulated division by zero")
    """
    )
    plugin_file = tmp_path / "crash_plugin.py"
    plugin_file.write_text(plugin_content, encoding="utf-8")

    res = run_plugin_in_sandbox(plugin_file, "hello", {})

    assert res.success is False
    assert res.result is None
    assert res.error is not None
    assert "ZeroDivisionError" in res.error


def test_sandbox_timeout(tmp_path):
    plugin_content = textwrap.dedent(
        """
        import time
        from pydantic import BaseModel

        class PluginMetadata(BaseModel):
            name: str
            version: str
            author: str

        class TestPlugin:
            metadata = PluginMetadata(name="TimeoutPlugin", version="1.0.0", author="Tester")

            def evaluate(self, text: str, context: dict):
                time.sleep(2)
                return {}
    """
    )
    plugin_file = tmp_path / "timeout_plugin.py"
    plugin_file.write_text(plugin_content, encoding="utf-8")

    res = run_plugin_in_sandbox(plugin_file, "hello", {}, timeout=1)

    assert res.success is False
    assert res.result is None
    assert res.error is not None
    assert "timeout" in res.error.lower()
