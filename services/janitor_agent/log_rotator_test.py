"""Tests for the log rotator module."""

import gzip
import os
import tempfile

import pytest

from services.janitor_agent.log_rotator import LogRotationConfig, LogRotator


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory with log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def _create_log_file(directory, name, size_bytes):
    """Create a log file with the given size."""
    path = os.path.join(directory, name)
    with open(path, "wb") as f:
        f.write(b"x" * size_bytes)
    return path


class TestLogRotator:
    def test_find_log_files(self, temp_log_dir):
        _create_log_file(temp_log_dir, "app.log", 100)
        _create_log_file(temp_log_dir, "error.log", 100)
        _create_log_file(temp_log_dir, "not-a-log.txt", 100)

        config = LogRotationConfig(log_dirs=[temp_log_dir], patterns=["*.log"])
        rotator = LogRotator(config)
        files = rotator.find_log_files()

        assert len(files) == 2
        assert any("app.log" in f for f in files)
        assert any("error.log" in f for f in files)

    def test_find_log_files_nonexistent_dir(self):
        config = LogRotationConfig(log_dirs=["/nonexistent/dir"], patterns=["*.log"])
        rotator = LogRotator(config)
        files = rotator.find_log_files()
        assert files == []

    def test_should_rotate_below_threshold(self, temp_log_dir):
        path = _create_log_file(temp_log_dir, "small.log", 100)
        config = LogRotationConfig(log_dirs=[temp_log_dir], max_size_bytes=1000)
        rotator = LogRotator(config)
        assert not rotator.should_rotate(path)

    def test_should_rotate_above_threshold(self, temp_log_dir):
        path = _create_log_file(temp_log_dir, "big.log", 2000)
        config = LogRotationConfig(log_dirs=[temp_log_dir], max_size_bytes=1000)
        rotator = LogRotator(config)
        assert rotator.should_rotate(path)

    def test_rotate_file_creates_compressed(self, temp_log_dir):
        path = _create_log_file(temp_log_dir, "rotate.log", 500)
        config = LogRotationConfig(
            log_dirs=[temp_log_dir],
            max_size_bytes=100,
            compress=True,
        )
        rotator = LogRotator(config)
        result = rotator.rotate_file(path)

        assert result.success
        assert result.action == "rotated"
        assert result.size_bytes == 500
        # Original file should be recreated empty
        assert os.path.exists(path)
        assert os.path.getsize(path) == 0
        # Compressed rotated file should exist
        gz_files = [f for f in os.listdir(temp_log_dir) if f.endswith(".gz")]
        assert len(gz_files) == 1

    def test_rotate_file_uncompressed(self, temp_log_dir):
        path = _create_log_file(temp_log_dir, "nocompress.log", 500)
        config = LogRotationConfig(
            log_dirs=[temp_log_dir],
            max_size_bytes=100,
            compress=False,
        )
        rotator = LogRotator(config)
        result = rotator.rotate_file(path)

        assert result.success
        # Should have original (empty) + rotated
        log_files = [
            f for f in os.listdir(temp_log_dir) if f.startswith("nocompress.log")
        ]
        assert len(log_files) == 2

    def test_rotate_file_to_archive_dir(self, temp_log_dir):
        archive_dir = os.path.join(temp_log_dir, "archive")
        path = _create_log_file(temp_log_dir, "archived.log", 500)
        config = LogRotationConfig(
            log_dirs=[temp_log_dir],
            max_size_bytes=100,
            compress=True,
            archive_dir=archive_dir,
        )
        rotator = LogRotator(config)
        result = rotator.rotate_file(path)

        assert result.success
        assert os.path.isdir(archive_dir)
        archived = os.listdir(archive_dir)
        assert len(archived) == 1
        assert archived[0].endswith(".gz")

    def test_cleanup_old_rotated_files(self, temp_log_dir):
        base_path = os.path.join(temp_log_dir, "cleanup.log")
        _create_log_file(temp_log_dir, "cleanup.log", 10)
        # Create 7 rotated files
        for i in range(7):
            _create_log_file(temp_log_dir, f"cleanup.log.2026010{i}000000.gz", 10)

        config = LogRotationConfig(log_dirs=[temp_log_dir], max_rotated_files=3)
        rotator = LogRotator(config)
        results = rotator.cleanup_old_rotated_files(base_path)

        # Should delete 4 (7 - 3)
        deleted = [r for r in results if r.action == "deleted" and r.success]
        assert len(deleted) == 4

    def test_run_full_cycle(self, temp_log_dir):
        # Create one big and one small log
        _create_log_file(temp_log_dir, "big.log", 2000)
        _create_log_file(temp_log_dir, "small.log", 50)

        config = LogRotationConfig(
            log_dirs=[temp_log_dir],
            patterns=["*.log"],
            max_size_bytes=1000,
            compress=True,
        )
        rotator = LogRotator(config)
        results = rotator.run()

        rotated = [r for r in results if r.action == "rotated"]
        skipped = [r for r in results if r.action == "skipped"]

        assert len(rotated) == 1
        assert rotated[0].success
        assert len(skipped) == 1

    def test_run_empty_dirs(self):
        config = LogRotationConfig(log_dirs=["/nonexistent"], patterns=["*.log"])
        rotator = LogRotator(config)
        results = rotator.run()
        assert results == []
