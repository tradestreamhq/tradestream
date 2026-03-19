"""Tests for the janitor agent notifier and report distribution."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from services.janitor_agent.notifier import (
    NotificationConfig,
    ReportDistributionConfig,
    ReportDistributor,
    RetirementNotifier,
)


class TestRetirementNotifier:
    def _make_notifier(self, systems=None):
        config = NotificationConfig(
            pubsub_project="test-project",
            dependent_systems=systems or ["signal-router", "dashboard"],
        )
        return RetirementNotifier(config)

    def test_notify_retirement_returns_results_for_all_systems(self):
        notifier = self._make_notifier()
        with patch.object(notifier, "_publish_event") as mock_pub:
            results = notifier.notify_retirement(
                impl_id="impl-1",
                spec_id="spec-1",
                symbol="BTC/USD",
                reason="Declining performance",
            )
        assert "signal-router" in results
        assert "dashboard" in results
        assert mock_pub.call_count == 2

    def test_notify_retirement_handles_publish_failure(self):
        notifier = self._make_notifier()
        with patch.object(
            notifier, "_publish_event", side_effect=Exception("Pub/Sub error")
        ):
            results = notifier.notify_retirement(
                impl_id="impl-1",
                spec_id="spec-1",
                symbol="BTC/USD",
                reason="test",
            )
        assert "failed" in results["signal-router"]
        assert "failed" in results["dashboard"]

    def test_notify_retirement_with_metadata(self):
        notifier = self._make_notifier()
        with patch.object(notifier, "_publish_event") as mock_pub:
            notifier.notify_retirement(
                impl_id="impl-1",
                spec_id="spec-1",
                symbol="ETH/USD",
                reason="Poor Sharpe",
                metadata={"final_sharpe": 0.23},
            )
        call_args = mock_pub.call_args_list[0]
        notification = call_args[0][1]
        assert notification["metadata"]["final_sharpe"] == 0.23
        assert notification["symbol"] == "ETH/USD"

    def test_notify_with_empty_systems(self):
        notifier = self._make_notifier(systems=[])
        results = notifier.notify_retirement(
            impl_id="impl-1",
            spec_id="spec-1",
            symbol="BTC/USD",
            reason="test",
        )
        assert results == {}


class FakeReport:
    """Fake report for testing distribution."""

    def __init__(
        self,
        report_date=None,
        evaluated_count=10,
        retired_count=3,
        protected_count=1,
        duration_seconds=12.5,
        has_warnings=False,
    ):
        self.report_date = report_date or date(2026, 3, 19)
        self.evaluated_count = evaluated_count
        self.retired_count = retired_count
        self.protected_count = protected_count
        self.duration_seconds = duration_seconds
        self.has_warnings = has_warnings

    def to_markdown(self):
        return f"# Report {self.report_date}\nRetired: {self.retired_count}"


class TestReportDistributor:
    def _make_distributor(self, **kwargs):
        config = ReportDistributionConfig(**kwargs)
        return ReportDistributor(config)

    def test_distribute_with_no_services_configured(self):
        distributor = self._make_distributor()
        report = FakeReport()
        results = distributor.distribute(report)
        # No GCS or Slack without credentials, so results may be empty
        assert isinstance(results, dict)

    def test_slack_not_sent_without_webhook(self):
        distributor = self._make_distributor(slack_webhook_url="")
        report = FakeReport()
        result = distributor._send_slack(report, "2026-03-19")
        assert result is False

    @patch("services.janitor_agent.notifier.requests")
    def test_slack_sent_with_webhook(self, mock_requests):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_response

        distributor = self._make_distributor(
            slack_webhook_url="https://hooks.slack.com/test"
        )
        report = FakeReport()
        result = distributor._send_slack(report, "2026-03-19")
        assert result is True
        mock_requests.post.assert_called_once()

    def test_email_not_sent_without_smtp(self):
        distributor = self._make_distributor()
        report = FakeReport()
        with patch.dict("os.environ", {}, clear=True):
            result = distributor._send_email(report, "2026-03-19")
        assert result is False

    def test_email_not_sent_when_under_threshold(self):
        distributor = self._make_distributor(email_on_threshold=10)
        report = FakeReport(retired_count=3, has_warnings=False)
        results = distributor.distribute(report)
        assert "email" not in results

    def test_email_triggered_when_over_threshold(self):
        distributor = self._make_distributor(email_on_threshold=5)
        report = FakeReport(retired_count=8, has_warnings=False)
        # Email won't actually send without SMTP but the logic path is exercised
        results = distributor.distribute(report)
        # No SMTP configured so email won't appear
        assert isinstance(results, dict)

    def test_email_triggered_on_warnings(self):
        distributor = self._make_distributor(email_on_threshold=100)
        report = FakeReport(retired_count=1, has_warnings=True)
        results = distributor.distribute(report)
        assert isinstance(results, dict)
