"""Tests for the Janitor Agent orchestrator."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.janitor_agent.agent import JanitorAgent, JanitorConfig
from services.janitor_agent.db_maintenance import MaintenanceConfig, MaintenanceResult
from services.janitor_agent.health_checker import HealthCheckConfig
from services.janitor_agent.retirement_criteria import RetirementConfig


def _make_config() -> JanitorConfig:
    return JanitorConfig(
        retirement=RetirementConfig(
            min_signals=100,
            min_age_days=180,
            max_sharpe=0.5,
            max_accuracy=0.45,
            max_retirements_per_run=50,
        ),
        maintenance=MaintenanceConfig(
            pg_connection_string="postgresql://test:test@localhost/test",
            stale_signal_days=365,
            stale_backtest_days=180,
        ),
        health_check=HealthCheckConfig(services={}),
    )


def _make_agent(mock_pg=None, mock_health=None, mock_repairer=None):
    """Helper to create a JanitorAgent with mocked dependencies."""
    config = _make_config()
    with (
        patch("services.janitor_agent.agent.PostgreSQLMaintenance"),
        patch("services.janitor_agent.agent.HealthChecker"),
        patch("services.janitor_agent.agent.StateRepairer"),
    ):
        agent = JanitorAgent(config)
    if mock_pg:
        agent._pg = mock_pg
    if mock_health:
        agent._health = mock_health
    if mock_repairer:
        agent._repairer = mock_repairer
    # Mock notifier and distributor to avoid real network calls
    agent._notifier = MagicMock()
    agent._distributor = MagicMock()
    agent._distributor.distribute.return_value = {}
    return agent


class TestJanitorAgent:
    def test_run_retirement_cycle_no_candidates(self):
        mock_pg = MagicMock()
        mock_pg.get_retirement_candidates.return_value = []
        mock_pg.get_active_implementation_count.return_value = 100

        agent = _make_agent(mock_pg=mock_pg)
        result = agent.run_retirement_cycle()
        assert result["evaluated_count"] == 0
        assert len(result["retired_implementations"]) == 0

    def test_run_retirement_cycle_with_candidate(self):
        mock_pg = MagicMock()
        mock_pg.get_retirement_candidates.return_value = [
            {
                "impl_id": "impl-001",
                "spec_id": "spec-001",
                "spec_name": "TEST_STRATEGY",
                "source": "LLM_GENERATED",
                "symbol": "BTC/USD",
                "forward_sharpe": 0.2,
                "forward_accuracy": 0.38,
                "forward_trades": 200,
                "created_at": datetime.now(timezone.utc) - timedelta(days=250),
                "updated_at": datetime.now(timezone.utc) - timedelta(days=60),
                "status": "VALIDATED",
                "preferred_regime": None,
            }
        ]
        mock_pg.get_sharpe_trend.return_value = "DECLINING"
        mock_pg.check_better_alternatives.return_value = True
        mock_pg.detect_market_regime.return_value = "ranging"
        mock_pg.get_active_implementation_count.return_value = 100
        mock_pg.execute_retirement.return_value = MaintenanceResult(
            operation="retire", success=True, details="OK", rows_affected=1
        )
        mock_pg._get_connection.return_value.cursor.return_value.fetchone.return_value = (
            None
        )

        agent = _make_agent(mock_pg=mock_pg)
        result = agent.run_retirement_cycle()
        assert result["evaluated_count"] == 1
        assert len(result["retired_implementations"]) == 1
        mock_pg.execute_retirement.assert_called_once()
        # Verify notification was sent
        agent._notifier.notify_retirement.assert_called_once()

    def test_run_retirement_cycle_protects_canonical(self):
        mock_pg = MagicMock()
        mock_pg.get_retirement_candidates.return_value = [
            {
                "impl_id": "impl-001",
                "spec_id": "spec-001",
                "spec_name": "RSI_REVERSAL",
                "source": "CANONICAL",
                "symbol": "BTC/USD",
                "forward_sharpe": 0.1,
                "forward_accuracy": 0.30,
                "forward_trades": 300,
                "created_at": datetime.now(timezone.utc) - timedelta(days=365),
                "updated_at": None,
                "status": "VALIDATED",
                "preferred_regime": None,
            }
        ]
        mock_pg.get_active_implementation_count.return_value = 100

        agent = _make_agent(mock_pg=mock_pg)
        result = agent.run_retirement_cycle()
        assert result["evaluated_count"] == 1
        assert len(result["retired_implementations"]) == 0
        assert len(result["protected_canonical"]) == 1
        mock_pg.execute_retirement.assert_not_called()

    def test_run_db_maintenance(self):
        mock_pg = MagicMock()
        mock_pg.vacuum_analyze.return_value = [
            MaintenanceResult(operation="vacuum", success=True, details="OK")
        ]
        mock_pg.cleanup_stale_signals.return_value = MaintenanceResult(
            operation="cleanup", success=True, details="OK", rows_affected=10
        )
        mock_pg.cleanup_stale_backtests.return_value = MaintenanceResult(
            operation="cleanup", success=True, details="OK", rows_affected=5
        )
        mock_pg.cleanup_orphaned_records.return_value = MaintenanceResult(
            operation="cleanup", success=True, details="OK", rows_affected=0
        )

        agent = _make_agent(mock_pg=mock_pg)
        results = agent.run_db_maintenance()
        assert len(results) >= 4

    def test_run_full_cycle(self):
        mock_pg = MagicMock()
        mock_pg.get_retirement_candidates.return_value = []
        mock_pg.get_active_implementation_count.return_value = 100
        mock_pg.vacuum_analyze.return_value = []
        mock_pg.cleanup_stale_signals.return_value = MaintenanceResult(
            operation="cleanup", success=True, details="OK"
        )
        mock_pg.cleanup_stale_backtests.return_value = MaintenanceResult(
            operation="cleanup", success=True, details="OK"
        )
        mock_pg.cleanup_orphaned_records.return_value = MaintenanceResult(
            operation="cleanup", success=True, details="OK"
        )
        mock_pg.save_report.return_value = MaintenanceResult(
            operation="save", success=True, details="OK"
        )

        mock_health = MagicMock()
        mock_health.check_all.return_value = []

        mock_repairer = MagicMock()
        mock_repairer.run_all_repairs.return_value = []

        agent = _make_agent(
            mock_pg=mock_pg, mock_health=mock_health, mock_repairer=mock_repairer
        )
        report = agent.run_full_cycle()
        assert report.report_date == date.today()
        assert report.evaluated_count == 0
        assert report.duration_seconds > 0
        mock_pg.save_report.assert_called_once()
        agent._distributor.distribute.assert_called_once()

    def test_run_retirement_cycle_defers_regime_mismatch(self):
        mock_pg = MagicMock()
        mock_pg.get_retirement_candidates.return_value = [
            {
                "impl_id": "impl-002",
                "spec_id": "spec-002",
                "spec_name": "MOMENTUM_STRAT",
                "source": "LLM_GENERATED",
                "symbol": "ETH/USD",
                "forward_sharpe": 0.2,
                "forward_accuracy": 0.38,
                "forward_trades": 200,
                "created_at": datetime.now(timezone.utc) - timedelta(days=250),
                "updated_at": datetime.now(timezone.utc) - timedelta(days=60),
                "status": "VALIDATED",
                "preferred_regime": "trending_up",
            }
        ]
        mock_pg.get_sharpe_trend.return_value = "DECLINING"
        mock_pg.check_better_alternatives.return_value = True
        mock_pg.detect_market_regime.return_value = "ranging"
        mock_pg.get_active_implementation_count.return_value = 100

        agent = _make_agent(mock_pg=mock_pg)
        result = agent.run_retirement_cycle()
        assert len(result["regime_deferred"]) == 1
        assert len(result["retired_implementations"]) == 0

    def test_reactivate_implementation(self):
        mock_pg = MagicMock()
        mock_pg.get_retirement_info.return_value = {
            "can_reactivate": True,
            "retired_at": datetime.now(timezone.utc) - timedelta(days=45),
        }
        mock_pg.get_reactivation_count.return_value = 0
        mock_pg.reactivate_implementation.return_value = MaintenanceResult(
            operation="reactivate", success=True, details="Reactivated"
        )

        agent = _make_agent(mock_pg=mock_pg)
        result = agent.reactivate_implementation(
            "impl-001", "Market regime changed", "admin"
        )
        assert result["success"] is True
        mock_pg.reactivate_implementation.assert_called_once()

    def test_reactivate_implementation_cooldown(self):
        mock_pg = MagicMock()
        mock_pg.get_retirement_info.return_value = {
            "can_reactivate": True,
            "retired_at": datetime.now(timezone.utc) - timedelta(days=10),
        }
        mock_pg.get_reactivation_count.return_value = 0

        agent = _make_agent(mock_pg=mock_pg)
        result = agent.reactivate_implementation("impl-001", "Testing", "admin")
        assert result["success"] is False
        assert "Cooling off" in result["error"]
