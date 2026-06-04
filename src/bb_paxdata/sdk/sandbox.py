# src/bb_paxdata/sdk/sandbox.py
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import textwrap
from dataclasses import dataclass

SANDBOX_TIMEOUT_SECONDS = 10


@dataclass
class SandboxResult:
    success: bool
    result: dict | None
    error: str | None


def run_plugin_in_sandbox(
    plugin_path: pathlib.Path,
    text: str,
    context: dict,
    timeout: int = SANDBOX_TIMEOUT_SECONDS,
) -> SandboxResult:
    """
    Plugin'i izole bir Python subprocess içinde çalıştırır.
    Plugin crash olsa bile ana process etkilenmez.
    """
    # Subprocess içinde çalışacak bootstrap kodu
    bootstrap = textwrap.dedent(
        f"""
        import sys, json, pathlib
        import importlib.util

        plugin_path = pathlib.Path({str(plugin_path)!r})
        spec = importlib.util.spec_from_file_location("plugin", plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Plugin sınıfını bul
        plugin_cls = None
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and hasattr(obj, 'evaluate') and hasattr(obj, 'metadata'):
                plugin_cls = obj
                break

        if plugin_cls is None:
            print(json.dumps({{"error": "No valid plugin class found"}}))
            sys.exit(1)

        instance = plugin_cls()
        if hasattr(instance, 'on_load'):
            instance.on_load()

        input_data = json.loads(sys.stdin.read())
        result = instance.evaluate(input_data["text"], input_data["context"])
        print(json.dumps(result.model_dump()))
    """
    )

    try:
        proc = subprocess.run(
            [sys.executable, "-c", bootstrap],
            input=json.dumps({"text": text, "context": context}),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        if proc.returncode != 0:
            return SandboxResult(success=False, result=None, error=proc.stderr[:1000])

        result = json.loads(proc.stdout.strip())
        if "error" in result:
            return SandboxResult(success=False, result=None, error=result["error"])

        return SandboxResult(success=True, result=result, error=None)

    except subprocess.TimeoutExpired:
        return SandboxResult(
            success=False, result=None, error=f"Plugin timeout ({timeout}s)"
        )
    except json.JSONDecodeError as e:
        return SandboxResult(
            success=False, result=None, error=f"Plugin output parse error: {e}"
        )
