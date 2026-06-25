"""
Windows Service wrapper for Process Manager.
Allows the process manager to run as a Windows service with auto-start on boot.
"""

import logging
import sys
from pathlib import Path

# Try to import pywin32, provide fallback if not available
try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    print("Warning: pywin32 not installed. Windows service functionality unavailable.")
    print("Install with: pip install pywin32")


class ProcessManagerService:
    """Windows Service for Process Manager."""

    _svc_name_ = "BBPAXDATAProcessManager"
    _svc_display_name_ = "BB-PAXDATA Process Manager"
    _svc_description_ = "Manages all BB-PAXDATA services without Docker"

    def __init__(self, args):
        if PYWIN32_AVAILABLE:
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            self.is_alive = True
        else:
            self.is_alive = False

    def SvcStop(self):
        """Stop the service."""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_alive = False
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STOPPED,
            (self._svc_name_, ""),
        )

    def SvcDoRun(self):
        """Main service loop."""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )

        self.main()

    def main(self):
        """Main service logic."""
        # Import here to avoid import errors if pywin32 not available
        import asyncio

        from process_manager import ProcessManager

        # Setup logging for service
        log_path = Path("logs/service.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
        )

        logger = logging.getLogger(__name__)
        logger.info("BB-PAXDATA Process Manager Service starting...")

        # Create and run process manager
        manager = ProcessManager()
        manager.running = True

        async def run_service():
            try:
                # Start all services
                await manager.start_all()

                # Start monitoring
                monitor_task = asyncio.create_task(manager.monitor_services())

                # Wait for stop event
                while self.is_alive:
                    await asyncio.sleep(1)

                # Cleanup
                monitor_task.cancel()
                await manager.stop_all()

                logger.info("BB-PAXDATA Process Manager Service stopped")

            except Exception as e:
                logger.error(f"Service error: {e}")
                await manager.stop_all()

        # Run the async service
        asyncio.run(run_service())


def install_service():
    """Install the Windows service."""
    if not PYWIN32_AVAILABLE:
        print("Error: pywin32 not installed. Cannot install service.")
        print("Install with: pip install pywin32")
        return False

    try:
        win32serviceutil.InstallService(
            None,
            ProcessManagerService._svc_name_,
            ProcessManagerService._svc_display_name_,
            startType=win32service.SERVICE_AUTO_START,
            description=ProcessManagerService._svc_description_,
        )
        print(
            f"Service '{ProcessManagerService._svc_display_name_}' installed successfully"
        )
        print("Service will start automatically on next boot")
        print("To start manually: python windows_service.py start")
        return True
    except Exception as e:
        print(f"Failed to install service: {e}")
        return False


def remove_service():
    """Remove the Windows service."""
    if not PYWIN32_AVAILABLE:
        print("Error: pywin32 not installed.")
        return False

    try:
        win32serviceutil.RemoveService(ProcessManagerService._svc_name_)
        print(
            f"Service '{ProcessManagerService._svc_display_name_}' removed successfully"
        )
        return True
    except Exception as e:
        print(f"Failed to remove service: {e}")
        return False


def start_service():
    """Start the Windows service."""
    if not PYWIN32_AVAILABLE:
        print("Error: pywin32 not installed.")
        return False

    try:
        win32serviceutil.StartService(ProcessManagerService._svc_name_)
        print(f"Service '{ProcessManagerService._svc_display_name_}' started")
        return True
    except Exception as e:
        print(f"Failed to start service: {e}")
        return False


def stop_service():
    """Stop the Windows service."""
    if not PYWIN32_AVAILABLE:
        print("Error: pywin32 not installed.")
        return False

    try:
        win32serviceutil.StopService(ProcessManagerService._svc_name_)
        print(f"Service '{ProcessManagerService._svc_display_name_}' stopped")
        return True
    except Exception as e:
        print(f"Failed to stop service: {e}")
        return False


def main():
    """Main entry point for Windows service management."""
    if len(sys.argv) < 2:
        print("Usage: python windows_service.py [install|remove|start|stop]")
        print("\nCommands:")
        print("  install  - Install as Windows service (auto-start on boot)")
        print("  remove   - Remove Windows service")
        print("  start    - Start the service")
        print("  stop     - Stop the service")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "install":
        success = install_service()
        sys.exit(0 if success else 1)

    elif command == "remove":
        success = remove_service()
        sys.exit(0 if success else 1)

    elif command == "start":
        success = start_service()
        sys.exit(0 if success else 1)

    elif command == "stop":
        success = stop_service()
        sys.exit(0 if success else 1)

    else:
        print(f"Unknown command: {command}")
        print("Usage: python windows_service.py [install|remove|start|stop]")
        sys.exit(1)


if __name__ == "__main__":
    if (
        PYWIN32_AVAILABLE
        and len(sys.argv) > 1
        and sys.argv[1].lower() not in ["install", "remove", "start", "stop"]
    ):
        # Running as service
        win32serviceutil.HandleCommandLine(ProcessManagerService)
    else:
        # Running as command-line tool
        main()
