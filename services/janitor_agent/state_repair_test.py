"""Tests for the state repair module."""

from unittest.mock import MagicMock, patch

import pytest

from services.janitor_agent.state_repair import RepairResult, StateRepairer


class TestRepairResult:
    def test_success_result(self):
        result = RepairResult(
            check_name="test",
            inconsistencies_found=5,
            repaired=5,
            details="Fixed 5 issues",
        )
        assert result.success is True
        assert result.inconsistencies_found == 5
        assert result.repaired == 5

    def test_failure_result(self):
        result = RepairResult(
            check_name="test",
            inconsistencies_found=0,
            repaired=0,
            details="Failed",
            success=False,
            error="Connection refused",
        )
        assert result.success is False
        assert result.error == "Connection refused"


class TestStateRepairer:
    @patch("services.janitor_agent.state_repair.StateRepairer._get_connection")
    def test_repair_orphaned_implementations(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.rowcount = 3
        mock_conn.return_value.cursor.return_value = mock_cursor

        repairer = StateRepairer("postgresql://test")
        result = repairer.repair_orphaned_implementations()

        assert result.success is True
        assert result.inconsistencies_found == 3
        assert result.repaired == 3
        assert "orphaned" in result.details.lower()

    @patch("services.janitor_agent.state_repair.StateRepairer._get_connection")
    def test_repair_orphaned_none_found(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_conn.return_value.cursor.return_value = mock_cursor

        repairer = StateRepairer("postgresql://test")
        result = repairer.repair_orphaned_implementations()

        assert result.success is True
        assert result.inconsistencies_found == 0
        assert result.repaired == 0

    @patch("services.janitor_agent.state_repair.StateRepairer._get_connection")
    def test_repair_stale_validated_status(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5,)
        mock_cursor.rowcount = 5
        mock_conn.return_value.cursor.return_value = mock_cursor

        repairer = StateRepairer("postgresql://test")
        result = repairer.repair_stale_validated_status()

        assert result.success is True
        assert result.inconsistencies_found == 5

    @patch("services.janitor_agent.state_repair.StateRepairer._get_connection")
    def test_repair_signal_impl_mismatch(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)
        mock_conn.return_value.cursor.return_value = mock_cursor

        repairer = StateRepairer("postgresql://test")
        result = repairer.repair_signal_impl_mismatch()

        assert result.success is True
        assert result.inconsistencies_found == 2
        assert result.repaired == 0  # Detection only

    @patch("services.janitor_agent.state_repair.StateRepairer._get_connection")
    def test_repair_duplicate_retirement_logs(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 4
        mock_conn.return_value.cursor.return_value = mock_cursor

        repairer = StateRepairer("postgresql://test")
        result = repairer.repair_duplicate_retirement_logs()

        assert result.success is True
        assert result.repaired == 4

    @patch("services.janitor_agent.state_repair.StateRepairer._get_connection")
    def test_handles_connection_error(self, mock_conn):
        mock_conn.side_effect = Exception("Connection refused")

        repairer = StateRepairer("postgresql://test")
        result = repairer.repair_orphaned_implementations()

        assert result.success is False
        assert "Connection refused" in result.error

    @patch("services.janitor_agent.state_repair.StateRepairer._get_connection")
    def test_run_all_repairs(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_cursor.rowcount = 0
        mock_conn.return_value.cursor.return_value = mock_cursor

        repairer = StateRepairer("postgresql://test")
        results = repairer.run_all_repairs()

        assert len(results) == 4
        assert all(r.success for r in results)
