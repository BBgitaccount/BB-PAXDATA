"""
Process Manager - Docker alternative for service orchestration.
Manages all BB-PAXDATA services without Docker.
"""

import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import psutil
from config import ServiceConfig, get_service_config, get_startup_order

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/process_manager.log"),
    ],
)
logger = logging.getLogger(__name__)


class ProcessInstance:
    """Represents一个 running process instance."""

    def __init__(self, config: ServiceConfig):
        self.config = config
        self.process: subprocess.Popen | None = None
        self.pid: int | None = None
        self.start_time: datetime | None = None
        self.restart_count = 0
        self.status = "stopped"  # stopped, starting, running, failed, stopping
        self.last_health_check: datetime | None = None
        self.health_status: bool | None = None

    def start(self) -> bool:
        """Start the process."""
        if self.status in ["running", "starting"]:
            logger.warning(f"Service {self.config.name} is already {self.status}")
            return True

        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(self.config.env_vars)

            # Prepare log file
            log_path = Path(self.config.log_file) if self.config.log_file else None
            if log_path:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_file = open(log_path, "a")
            else:
                log_file = subprocess.DEVNULL

            # Prepare working directory
            work_dir = Path(self.config.working_dir)
            work_dir.mkdir(parents=True, exist_ok=True)

            # Build command based on service type
            if self.config.service_type.value == "python":
                cmd = ["poetry", "run", *self.config.command.split()]
            elif self.config.service_type.value == "node":
                cmd = ["npm", *self.config.command.split()]
            else:
                cmd = self.config.command.split()

            logger.info(f"Starting {self.config.name} with command: {' '.join(cmd)}")

            # Start process
            self.process = subprocess.Popen(
                cmd,
                cwd=work_dir,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                shell=False if self.config.service_type.value != "system" else True,
            )

            self.pid = self.process.pid
            self.start_time = datetime.now()
            self.status = "starting"

            logger.info(f"Started {self.config.name} with PID {self.pid}")
            return True

        except Exception as e:
            logger.error(f"Failed to start {self.config.name}: {e}")
            self.status = "failed"
            return False

    def stop(self, timeout: int = 30) -> bool:
        """Stop the process gracefully."""
        if self.status == "stopped":
            return True

        self.status = "stopping"

        try:
            if self.process and self.process.poll() is None:
                # Try graceful shutdown
                self.process.terminate()

                # Wait for process to exit
                try:
                    self.process.wait(timeout=timeout)
                    logger.info(f"Stopped {self.config.name} gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if graceful shutdown fails
                    logger.warning(f"Force killing {self.config.name}")
                    self.process.kill()
                    self.process.wait()
                    logger.info(f"Force killed {self.config.name}")

            self.status = "stopped"
            self.process = None
            self.pid = None
            return True

        except Exception as e:
            logger.error(f"Failed to stop {self.config.name}: {e}")
            return False

    def restart(self) -> bool:
        """Restart the process."""
        logger.info(f"Restarting {self.config.name}")
        if self.stop():
            time.sleep(self.config.restart_delay)
            return self.start()
        return False

    def is_alive(self) -> bool:
        """Check if process is still running."""
        if self.process is None:
            return False

        if self.process.poll() is not None:
            return False

        # Also check via psutil for more reliability
        if self.pid:
            try:
                return psutil.pid_exists(self.pid)
            except Exception:
                return False

        return False

    async def health_check(self) -> bool:
        """Perform health check on the service."""
        if not self.config.health_check_url:
            # If no health check URL, check if process is alive
            return self.is_alive()

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.config.health_check_url)
                is_healthy = response.status_code < 400
                self.health_status = is_healthy
                self.last_health_check = datetime.now()
                return is_healthy
        except Exception as e:
            logger.debug(f"Health check failed for {self.config.name}: {e}")
            self.health_status = False
            self.last_health_check = datetime.now()
            return False


class ProcessManager:
    """Main process manager orchestrating all services."""

    def __init__(self):
        self.processes: dict[str, ProcessInstance] = {}
        self.running = False
        self.shutdown_event = asyncio.Event()

        # Create logs directory
        Path("logs").mkdir(exist_ok=True)

    def get_process(self, name: str) -> ProcessInstance:
        """Get or create process instance."""
        if name not in self.processes:
            config = get_service_config(name)
            self.processes[name] = ProcessInstance(config)
        return self.processes[name]

    async def start_service(self, name: str) -> bool:
        """Start a single service with dependency checking."""
        config = get_service_config(name)

        # Check dependencies
        for dep in config.dependencies:
            dep_process = self.get_process(dep)
            if dep_process.status != "running":
                logger.warning(f"Dependency {dep} not running, starting it first")
                if not await self.start_service(dep):
                    logger.error(f"Failed to start dependency {dep}")
                    return False

        process = self.get_process(name)

        if not process.start():
            return False

        # Wait for startup timeout
        start_time = time.time()
        while time.time() - start_time < config.startup_timeout:
            if process.is_alive():
                process.status = "running"
                logger.info(f"Service {name} is running")
                return True
            await asyncio.sleep(1)

        logger.error(f"Service {name} failed to start within timeout")
        process.status = "failed"
        return False

    async def stop_service(self, name: str) -> bool:
        """Stop a single service."""
        process = self.get_process(name)
        return process.stop()

    async def restart_service(self, name: str) -> bool:
        """Restart a single service."""
        process = self.get_process(name)
        return process.restart()

    async def start_all(self) -> bool:
        """Start all services in dependency order."""
        logger.info("Starting all services...")

        order = get_startup_order()

        for name in order:
            logger.info(f"Starting {name}...")
            if not await self.start_service(name):
                logger.error(f"Failed to start {name}, aborting")
                return False

            # Wait a bit between services
            await asyncio.sleep(2)

        logger.info("All services started successfully")
        return True

    async def stop_all(self) -> bool:
        """Stop all services in reverse dependency order."""
        logger.info("Stopping all services...")

        order = get_startup_order()
        reverse_order = list(reversed(order))

        for name in reverse_order:
            logger.info(f"Stopping {name}...")
            await self.stop_service(name)

        logger.info("All services stopped")
        return True

    async def monitor_services(self):
        """Continuously monitor service health and auto-restart if needed."""
        logger.info("Starting service monitoring...")

        while self.running and not self.shutdown_event.is_set():
            for name, process in self.processes.items():
                if process.status != "running":
                    continue

                # Perform health check
                is_healthy = await process.health_check()

                if not is_healthy:
                    logger.warning(f"Service {name} is unhealthy")

                    # Check if process is still alive
                    if not process.is_alive():
                        logger.error(f"Service {name} died unexpectedly")

                        # Auto-restart if enabled
                        if (
                            process.config.auto_restart
                            and process.restart_count < process.config.max_restarts
                        ):
                            process.restart_count += 1
                            logger.info(
                                f"Auto-restarting {name} (attempt {process.restart_count}/{process.config.max_restarts})"
                            )
                            await asyncio.sleep(process.config.restart_delay)
                            await self.start_service(name)
                        else:
                            logger.error(
                                f"Service {name} exceeded max restarts or auto-restart disabled"
                            )
                            process.status = "failed"

            # Sleep before next check
            await asyncio.sleep(10)

    async def status(self) -> dict[str, dict]:
        """Get status of all services."""
        status = {}
        for name, process in self.processes.items():
            status[name] = {
                "status": process.status,
                "pid": process.pid,
                "start_time": (
                    process.start_time.isoformat() if process.start_time else None
                ),
                "restart_count": process.restart_count,
                "health_status": process.health_status,
                "last_health_check": (
                    process.last_health_check.isoformat()
                    if process.last_health_check
                    else None
                ),
            }
        return status

    def print_status(self):
        """Print status of all services to console."""
        print("\n" + "=" * 80)
        print("SERVICE STATUS".center(80))
        print("=" * 80)

        for name in get_startup_order():
            if name in self.processes:
                proc = self.processes[name]
                status_line = f"{name:20} | {proc.status:10} | PID: {proc.pid or 'N/A':6} | Restarts: {proc.restart_count}"
                if proc.health_status is not None:
                    status_line += (
                        f" | Health: {'OK' if proc.health_status else 'FAIL'}"
                    )
                print(status_line)
            else:
                print(f"{name:20} | NOT STARTED")

        print("=" * 80 + "\n")


async def main():
    """Main entry point."""
    manager = ProcessManager()

    # Handle signals
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        manager.running = False
        manager.shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Parse command
    if len(sys.argv) < 2:
        print("Usage: python process_manager.py [start|stop|restart|status|monitor]")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "start":
        manager.running = True
        success = await manager.start_all()
        if success:
            print("All services started. Run 'monitor' to keep them running.")
        sys.exit(0 if success else 1)

    elif command == "stop":
        success = await manager.stop_all()
        sys.exit(0 if success else 1)

    elif command == "restart":
        await manager.stop_all()
        await asyncio.sleep(5)
        success = await manager.start_all()
        sys.exit(0 if success else 1)

    elif command == "status":
        manager.print_status()
        sys.exit(0)

    elif command == "monitor":
        manager.running = True
        success = await manager.start_all()
        if not success:
            logger.error("Failed to start services")
            sys.exit(1)

        # Start monitoring
        monitor_task = asyncio.create_task(manager.monitor_services())

        # Wait for shutdown
        await manager.shutdown_event.wait()

        # Cancel monitoring
        monitor_task.cancel()

        # Stop all services
        await manager.stop_all()

        logger.info("Process manager shutdown complete")
        sys.exit(0)

    else:
        print(f"Unknown command: {command}")
        print("Usage: python process_manager.py [start|stop|restart|status|monitor]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
