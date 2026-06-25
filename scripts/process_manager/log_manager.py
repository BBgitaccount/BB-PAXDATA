"""
Log management for process manager.
Handles log rotation, aggregation, and cleanup.
"""

import gzip
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class LogManager:
    """Manages log files for all services."""

    def __init__(
        self, log_dir: str = "logs", max_size_mb: int = 100, max_age_days: int = 30
    ):
        self.log_dir = Path(log_dir)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_age = timedelta(days=max_age_days)

        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def get_log_files(self) -> list[Path]:
        """Get all log files in the log directory."""
        return list(self.log_dir.glob("*.log"))

    def get_log_size(self, log_file: Path) -> int:
        """Get size of a log file in bytes."""
        try:
            return log_file.stat().st_size
        except OSError:
            return 0

    def should_rotate(self, log_file: Path) -> bool:
        """Check if a log file should be rotated based on size."""
        return self.get_log_size(log_file) > self.max_size_bytes

    def rotate_log(self, log_file: Path) -> bool:
        """Rotate a log file by compressing it and creating a new one."""
        try:
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{log_file.stem}_{timestamp}.log.gz"
            backup_path = self.log_dir / backup_name

            # Compress the log file
            with open(log_file, "rb") as f_in:
                with gzip.open(backup_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Clear the original log file
            with open(log_file, "w") as f:
                f.truncate()

            logger.info(f"Rotated log file: {log_file.name} -> {backup_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to rotate log file {log_file}: {e}")
            return False

    def should_delete(self, log_file: Path) -> bool:
        """Check if a log file should be deleted based on age."""
        try:
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            age = datetime.now() - mtime
            return age > self.max_age
        except OSError:
            return False

    def delete_old_logs(self) -> int:
        """Delete log files older than max_age."""
        deleted_count = 0

        for log_file in self.get_log_files():
            if self.should_delete(log_file):
                try:
                    log_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old log file: {log_file.name}")
                except Exception as e:
                    logger.error(f"Failed to delete {log_file}: {e}")

        return deleted_count

    def rotate_all_logs(self) -> int:
        """Rotate all log files that exceed max size."""
        rotated_count = 0

        for log_file in self.get_log_files():
            if self.should_rotate(log_file):
                if self.rotate_log(log_file):
                    rotated_count += 1

        return rotated_count

    def cleanup(self) -> dict:
        """Perform full log cleanup: rotate large logs and delete old ones."""
        logger.info("Starting log cleanup...")

        rotated = self.rotate_all_logs()
        deleted = self.delete_old_logs()

        result = {
            "rotated": rotated,
            "deleted": deleted,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"Log cleanup complete: {rotated} rotated, {deleted} deleted")
        return result

    def aggregate_logs(self, output_file: str = "logs/aggregated.log") -> bool:
        """Aggregate all log files into a single file."""
        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as out_f:
                for log_file in sorted(self.get_log_files()):
                    out_f.write(f"\n{'='*80}\n")
                    out_f.write(f"File: {log_file.name}\n")
                    out_f.write(f"{'='*80}\n\n")

                    with open(log_file) as in_f:
                        shutil.copyfileobj(in_f, out_f)

            logger.info(f"Aggregated logs to: {output_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to aggregate logs: {e}")
            return False

    def get_log_stats(self) -> dict:
        """Get statistics about log files."""
        stats = {"total_files": 0, "total_size_bytes": 0, "files": []}

        for log_file in self.get_log_files():
            size = self.get_log_size(log_file)
            try:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            except OSError:
                mtime = None

            stats["total_files"] += 1
            stats["total_size_bytes"] += size
            stats["files"].append(
                {
                    "name": log_file.name,
                    "size_bytes": size,
                    "size_mb": round(size / (1024 * 1024), 2),
                    "modified": mtime.isoformat() if mtime else None,
                }
            )

        stats["total_size_mb"] = round(stats["total_size_bytes"] / (1024 * 1024), 2)

        return stats


def setup_log_rotation():
    """Setup automatic log rotation for process manager."""
    log_manager = LogManager()

    # Perform initial cleanup
    log_manager.cleanup()

    return log_manager
