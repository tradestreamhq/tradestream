"""Log rotation and archival for TradeStream services.

Manages log file rotation, compression, and cleanup across all services.
Supports configurable retention periods and archive destinations.
"""

import glob
import gzip
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from absl import logging


@dataclass
class LogRotationConfig:
    """Configuration for log rotation."""

    # Directories to scan for log files
    log_dirs: list[str] = field(
        default_factory=lambda: [
            "/var/log/tradestream",
            "/var/log/tradestream/services",
        ]
    )
    # File patterns to rotate
    patterns: list[str] = field(
        default_factory=lambda: ["*.log", "*.json.log"]
    )
    # Maximum size in bytes before rotation (100MB default)
    max_size_bytes: int = 100 * 1024 * 1024
    # Maximum age in days before cleanup
    max_age_days: int = 30
    # Number of rotated files to keep per log
    max_rotated_files: int = 5
    # Compress rotated files
    compress: bool = True
    # Archive directory (None = same directory as log)
    archive_dir: Optional[str] = None


@dataclass
class RotationResult:
    """Result of a log rotation operation."""

    file_path: str
    action: str  # "rotated", "compressed", "deleted", "skipped"
    success: bool
    details: str
    size_bytes: int = 0
    error: Optional[str] = None


class LogRotator:
    """Handles log rotation, compression, and archival."""

    def __init__(self, config: LogRotationConfig):
        self._config = config

    def find_log_files(self) -> list[str]:
        """Find all log files matching configured patterns."""
        files = []
        for log_dir in self._config.log_dirs:
            if not os.path.isdir(log_dir):
                continue
            for pattern in self._config.patterns:
                matched = glob.glob(os.path.join(log_dir, pattern))
                files.extend(matched)
        return sorted(set(files))

    def should_rotate(self, file_path: str) -> bool:
        """Check if a log file needs rotation based on size."""
        try:
            size = os.path.getsize(file_path)
            return size >= self._config.max_size_bytes
        except OSError:
            return False

    def rotate_file(self, file_path: str) -> RotationResult:
        """Rotate a single log file by renaming and optionally compressing."""
        try:
            size = os.path.getsize(file_path)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

            if self._config.archive_dir:
                os.makedirs(self._config.archive_dir, exist_ok=True)
                base_name = os.path.basename(file_path)
                rotated_path = os.path.join(
                    self._config.archive_dir, f"{base_name}.{timestamp}"
                )
            else:
                rotated_path = f"{file_path}.{timestamp}"

            # Move the current log file
            shutil.move(file_path, rotated_path)

            # Create a new empty log file with same permissions
            with open(file_path, "w"):
                pass

            # Compress if configured
            if self._config.compress:
                compressed_path = f"{rotated_path}.gz"
                with open(rotated_path, "rb") as f_in:
                    with gzip.open(compressed_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(rotated_path)
                rotated_path = compressed_path

            logging.info(
                "Rotated log %s (%d bytes) -> %s", file_path, size, rotated_path
            )
            return RotationResult(
                file_path=file_path,
                action="rotated",
                success=True,
                details=f"Rotated to {rotated_path}",
                size_bytes=size,
            )
        except Exception as e:
            logging.error("Failed to rotate %s: %s", file_path, e)
            return RotationResult(
                file_path=file_path,
                action="rotated",
                success=False,
                details=f"Failed to rotate {file_path}",
                error=str(e),
            )

    def cleanup_old_rotated_files(self, base_path: str) -> list[RotationResult]:
        """Remove rotated log files beyond the retention limit."""
        results = []
        dir_path = self._config.archive_dir or os.path.dirname(base_path)
        base_name = os.path.basename(base_path)

        # Find all rotated versions of this log file
        pattern = os.path.join(dir_path, f"{base_name}.*")
        rotated_files = sorted(glob.glob(pattern), reverse=True)

        # Keep only max_rotated_files, delete the rest
        for old_file in rotated_files[self._config.max_rotated_files :]:
            try:
                size = os.path.getsize(old_file)
                os.remove(old_file)
                logging.info("Deleted old rotated log: %s", old_file)
                results.append(
                    RotationResult(
                        file_path=old_file,
                        action="deleted",
                        success=True,
                        details=f"Deleted old rotated file (beyond {self._config.max_rotated_files} limit)",
                        size_bytes=size,
                    )
                )
            except Exception as e:
                logging.error("Failed to delete old rotated log %s: %s", old_file, e)
                results.append(
                    RotationResult(
                        file_path=old_file,
                        action="deleted",
                        success=False,
                        details=f"Failed to delete {old_file}",
                        error=str(e),
                    )
                )

        return results

    def cleanup_aged_files(self) -> list[RotationResult]:
        """Remove any log files (including rotated) older than max_age_days."""
        results = []
        now = datetime.now(timezone.utc).timestamp()
        max_age_seconds = self._config.max_age_days * 86400

        for log_dir in self._config.log_dirs:
            if not os.path.isdir(log_dir):
                continue
            for entry in os.listdir(log_dir):
                full_path = os.path.join(log_dir, entry)
                if not os.path.isfile(full_path):
                    continue
                # Only clean up rotated/compressed files
                if not (entry.endswith(".gz") or "." in entry.rsplit(".log", 1)[-1]):
                    continue
                try:
                    mtime = os.path.getmtime(full_path)
                    age_seconds = now - mtime
                    if age_seconds > max_age_seconds:
                        size = os.path.getsize(full_path)
                        os.remove(full_path)
                        age_days = int(age_seconds / 86400)
                        logging.info(
                            "Deleted aged log %s (%d days old)", full_path, age_days
                        )
                        results.append(
                            RotationResult(
                                file_path=full_path,
                                action="deleted",
                                success=True,
                                details=f"Deleted log aged {age_days} days (max {self._config.max_age_days})",
                                size_bytes=size,
                            )
                        )
                except Exception as e:
                    logging.error("Failed to clean up %s: %s", full_path, e)
                    results.append(
                        RotationResult(
                            file_path=full_path,
                            action="deleted",
                            success=False,
                            details=f"Failed to delete {full_path}",
                            error=str(e),
                        )
                    )

        return results

    def run(self) -> list[RotationResult]:
        """Run full log rotation cycle: rotate oversized files, clean up old ones."""
        results = []
        log_files = self.find_log_files()
        logging.info("Found %d log files to check", len(log_files))

        # Rotate oversized files
        for log_file in log_files:
            if self.should_rotate(log_file):
                result = self.rotate_file(log_file)
                results.append(result)
                if result.success:
                    cleanup = self.cleanup_old_rotated_files(log_file)
                    results.extend(cleanup)
            else:
                results.append(
                    RotationResult(
                        file_path=log_file,
                        action="skipped",
                        success=True,
                        details="Below size threshold",
                        size_bytes=os.path.getsize(log_file)
                        if os.path.exists(log_file)
                        else 0,
                    )
                )

        # Clean up aged files
        aged_results = self.cleanup_aged_files()
        results.extend(aged_results)

        rotated = sum(1 for r in results if r.action == "rotated" and r.success)
        deleted = sum(1 for r in results if r.action == "deleted" and r.success)
        logging.info(
            "Log rotation complete: %d rotated, %d deleted", rotated, deleted
        )
        return results
