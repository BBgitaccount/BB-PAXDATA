# src/bb_paxdata/sdk/watcher.py
from __future__ import annotations

import pathlib
import threading

import structlog
from bb_paxdata.sdk.registry import PluginRegistry
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = structlog.get_logger(__name__)


class PluginFileHandler(FileSystemEventHandler):
    """
    FileSystemEventHandler that coordinates with PluginRegistry to load,
    reload, and unload plugins dynamically as files change.
    """

    def __init__(self, registry: PluginRegistry, directory: pathlib.Path) -> None:
        super().__init__()
        self.registry = registry
        self.directory = directory.resolve()
        self._path_to_name: dict[pathlib.Path, str] = {}
        self._lock = threading.Lock()

        # Initial scan to load any plugins already present in the directory
        self.scan_existing()

    def scan_existing(self) -> None:
        """Scan directory and register all existing python file plugins."""
        with self._lock:
            for path in self.directory.glob("*.py"):
                if path.is_file():
                    self._load_path(path)

    def _load_path(self, path: pathlib.Path) -> None:
        path = path.resolve()
        old_name = self._path_to_name.get(path)

        entry = self.registry.register(path)
        if entry:
            new_name = entry.metadata.name
            if old_name and old_name != new_name:
                self.registry.unregister(old_name)
            self._path_to_name[path] = new_name
            logger.info("Loaded/Reloaded plugin from %s: %s", path.name, new_name)
        else:
            logger.warning("Failed to load plugin from %s", path.name)

    def _unload_path(self, path: pathlib.Path) -> None:
        path = path.resolve()
        old_name = self._path_to_name.pop(path, None)
        if old_name:
            self.registry.unregister(old_name)
            logger.info("Unloaded plugin: %s (file deleted: %s)", old_name, path.name)

    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".py"):
            return
        path = pathlib.Path(event.src_path)
        with self._lock:
            self._load_path(path)

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith(".py"):
            return
        path = pathlib.Path(event.src_path)
        with self._lock:
            self._load_path(path)

    def on_deleted(self, event):
        if event.is_directory or not event.src_path.endswith(".py"):
            return
        path = pathlib.Path(event.src_path)
        with self._lock:
            self._unload_path(path)

    def on_moved(self, event):
        if event.is_directory:
            return
        src_path = pathlib.Path(event.src_path)
        dest_path = pathlib.Path(event.dest_path)

        with self._lock:
            if src_path.suffix == ".py":
                self._unload_path(src_path)
            if dest_path.suffix == ".py":
                self._load_path(dest_path)


class PluginWatcher:
    """
    Manages the lifecycle of a directory observer for plugins.
    """

    def __init__(self, registry: PluginRegistry, directory: pathlib.Path | str) -> None:
        self.registry = registry
        self.directory = pathlib.Path(directory).resolve()
        self.handler = PluginFileHandler(self.registry, self.directory)
        self.observer = Observer()

    def start(self) -> None:
        """Start the watchdog observer."""
        self.observer.schedule(self.handler, path=str(self.directory), recursive=False)
        self.observer.start()
        logger.info("Started watching plugin directory: %s", self.directory)

    def stop(self) -> None:
        """Stop the watchdog observer and wait for thread to terminate."""
        self.observer.stop()
        self.observer.join()
        logger.info("Stopped watching plugin directory: %s", self.directory)
