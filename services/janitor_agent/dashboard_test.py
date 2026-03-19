"""Tests for the dashboard data provider module."""

from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

import pytest

from services.janitor_agent.dashboard import DashboardData, DashboardProvider


class TestDashboardData:
    def test_default_values(self):
        data = DashboardData()
        assert data.last_run_at is None
        assert data.total_retired_implementations == 0
        assert data.services_healthy == 0
        assert data.recent_reports == []

    def test_custom_values(self):
        data = DashboardData(
            total_retired_implementations=15,
            total_retired_specs=3,
            retirements_last_7_days=5,
            services_healthy=10,
            services_unhealthy=1,
        )
        assert data.total_retired_implementations == 15
        assert data.total_retired_specs == 3
        assert data.retirements_last_7_days == 5
        assert data.services_healthy == 10


class TestDashboardProvider:
    @patch("services.janitor_agent.dashboard.DashboardProvider._get_connection")
    def test_get_dashboard_data_with_results(self, mock_conn):
        cur = MagicMock()

        # Mock last report query
        report_time = datetime(2026, 3, 19, 3, 0, 0, tzinfo=timezone.utc)
        cur.fetchone.side_effect = [
            # Last report
            ("2026-03-19", 47, 12, 2, 3, report_time),
            # Total retirements
            (120, 8),
            # Last 7 days retirements
            (5,),
            # Last 7 days reactivations
            (1,),
        ]
        cur.fetchall.return_value = [
            ("2026-03-19", 47, 12, 2, 3),
            ("2026-03-18", 35, 8, 1, 2),
        ]

        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_conn.return_value)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value = cur

        provider = DashboardProvider("postgresql://localhost/test")
        data = provider.get_dashboard_data()

        assert data.last_run_at == report_time.isoformat()
        assert data.total_retired_implementations == 120
        assert data.total_retired_specs == 8
        assert data.retirements_last_7_days == 5
        assert data.reactivations_last_7_days == 1
        assert len(data.recent_reports) == 2

    @patch("services.janitor_agent.dashboard.DashboardProvider._get_connection")
    def test_get_dashboard_data_empty_db(self, mock_conn):
        cur = MagicMock()
        cur.fetchone.side_effect = [None, (0, 0), (0,), (0,)]
        cur.fetchall.return_value = []

        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_conn.return_value)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value = cur

        provider = DashboardProvider("postgresql://localhost/test")
        data = provider.get_dashboard_data()

        assert data.last_run_at is None
        assert data.total_retired_implementations == 0
        assert data.recent_reports == []

    @patch("services.janitor_agent.dashboard.DashboardProvider._get_connection")
    def test_get_dashboard_data_connection_error(self, mock_conn):
        mock_conn.side_effect = Exception("Connection refused")

        provider = DashboardProvider("postgresql://localhost/test")
        data = provider.get_dashboard_data()

        # Should return empty data, not raise
        assert data.total_retired_implementations == 0

    def test_get_dashboard_json_structure(self):
        provider = DashboardProvider.__new__(DashboardProvider)
        provider._conn_string = ""

        data = DashboardData(
            total_retired_implementations=10,
            services_healthy=5,
            services_unhealthy=1,
            logs_rotated=3,
        )

        # Monkey-patch get_dashboard_data to return our test data
        provider.get_dashboard_data = lambda: data
        result = provider.get_dashboard_json()

        assert "last_run" in result
        assert "retirements" in result
        assert "cleanup" in result
        assert "health" in result
        assert "state_repair" in result
        assert "log_rotation" in result
        assert "recent_reports" in result
        assert result["retirements"]["total_implementations"] == 10
        assert result["health"]["healthy"] == 5
        assert result["log_rotation"]["rotated"] == 3
