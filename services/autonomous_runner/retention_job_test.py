"""Tests for the retention job runner."""

import time

import pytest

from services.autonomous_runner.retention import RetentionConfig
from services.autonomous_runner.retention_job import (
    RetentionJob,
    RetentionJobConfig,
    RetentionJobResult,
)


class TestRetentionJobResult:
    def test_initial_state(self):
        result = RetentionJobResult()
        assert result.archived_count == 0
        assert result.deleted_decisions_count == 0
        assert result.errors == []
        assert result.completed_at is None

    def test_complete_sets_timestamp(self):
        result = RetentionJobResult()
        result.complete()
        assert result.completed_at is not None
        assert result.duration_ms >= 0

    def test_to_dict(self):
        result = RetentionJobResult()
        result.archived_count = 10
        result.deleted_decisions_count = 5
        result.complete()

        d = result.to_dict()
        assert d["archived_count"] == 10
        assert d["deleted_decisions_count"] == 5
        assert d["errors"] == []
        assert d["duration_ms"] >= 0
        assert d["dry_run"] is False


class TestRetentionJobConfig:
    def test_defaults(self):
        config = RetentionJobConfig()
        assert config.interval_hours == 24
        assert config.dry_run is False
        assert config.retention is not None
        assert config.retention.hot_retention_days == 30

    def test_custom_retention(self):
        retention = RetentionConfig(hot_retention_days=7, warm_retention_days=30)
        config = RetentionJobConfig(retention=retention)
        assert config.retention.hot_retention_days == 7


class TestRetentionJob:
    def setup_method(self):
        self.job = RetentionJob(db_pool=None)

    def test_is_available_without_pool(self):
        assert self.job.is_available is False

    def test_should_run_first_time(self):
        assert self.job.should_run() is True

    def test_should_run_after_interval(self):
        self.job._last_run_at = time.time() - (25 * 3600)  # 25 hours ago
        assert self.job.should_run() is True

    def test_should_not_run_before_interval(self):
        self.job._last_run_at = time.time() - (1 * 3600)  # 1 hour ago
        assert self.job.should_run() is False

    def test_execute_without_db(self):
        result = self.job.execute()
        assert len(result.errors) == 1
        assert "Database not available" in result.errors[0]
        assert result.completed_at is not None

    def test_execute_dry_run_without_db(self):
        result = self.job.execute(dry_run=True)
        assert len(result.errors) == 1
        assert result.dry_run is True

    def test_get_status_initial(self):
        status = self.job.get_status()
        assert status["last_run_at"] is None
        assert status["total_runs"] == 0
        assert status["interval_hours"] == 24
        assert status["last_result"] is None
        assert status["db_available"] is False

    def test_get_status_after_run(self):
        self.job.execute()
        status = self.job.get_status()
        assert status["total_runs"] == 1
        assert status["last_run_at"] is not None
        assert status["last_result"] is not None

    def test_execute_increments_total_runs(self):
        self.job.execute()
        self.job.execute()
        assert self.job._total_runs == 2

    def test_custom_interval(self):
        config = RetentionJobConfig(interval_hours=6)
        job = RetentionJob(config=config)
        job._last_run_at = time.time() - (7 * 3600)
        assert job.should_run() is True
        job._last_run_at = time.time() - (5 * 3600)
        assert job.should_run() is False
