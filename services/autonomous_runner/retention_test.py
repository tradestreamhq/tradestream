"""Tests for the retention policy manager."""

from services.autonomous_runner.retention import RetentionConfig, RetentionManager


def test_default_config():
    mgr = RetentionManager()
    assert mgr.config.hot_retention_days == 30
    assert mgr.config.warm_retention_days == 90
    assert mgr.config.archive_enabled is True


def test_custom_config():
    cfg = RetentionConfig(hot_retention_days=7, warm_retention_days=30)
    mgr = RetentionManager(cfg)
    assert mgr.config.hot_retention_days == 7
    assert mgr.config.warm_retention_days == 30


def test_cleanup_sql_generates_statements():
    mgr = RetentionManager()
    stmts = mgr.get_cleanup_sql()
    assert len(stmts) >= 4
    # Check statement names
    names = [s[0] for s in stmts]
    assert "count_expired" in names
    assert "delete_expired_feedback" in names
    assert "delete_expired_outcomes" in names
    assert "delete_expired_decisions" in names


def test_cleanup_sql_uses_configured_days():
    cfg = RetentionConfig(warm_retention_days=60)
    mgr = RetentionManager(cfg)
    stmts = mgr.get_cleanup_sql()
    # All SQL should reference 60 days
    for _, sql in stmts:
        if "INTERVAL" in sql:
            assert "60 days" in sql


def test_cleanup_sql_includes_vacuum_when_enabled():
    cfg = RetentionConfig(vacuum_after_delete=True)
    mgr = RetentionManager(cfg)
    stmts = mgr.get_cleanup_sql()
    names = [s[0] for s in stmts]
    assert "vacuum_decisions" in names


def test_cleanup_sql_excludes_vacuum_when_disabled():
    cfg = RetentionConfig(vacuum_after_delete=False)
    mgr = RetentionManager(cfg)
    stmts = mgr.get_cleanup_sql()
    names = [s[0] for s in stmts]
    assert "vacuum_decisions" not in names


def test_archive_query():
    mgr = RetentionManager()
    query = mgr.get_archive_query()
    assert "agent_decisions" in query
    assert "90 days" in query
    assert "decision_id" in query


def test_get_status():
    mgr = RetentionManager()
    status = mgr.get_status()
    assert status["hot_retention_days"] == 30
    assert status["warm_retention_days"] == 90
    assert status["archive_enabled"] is True
    assert "archive_destination" in status
