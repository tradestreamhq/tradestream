"""Tests for the Regime Change Alerter."""

from unittest import mock

import pytest

from services.learning_engine.regime_alerter import RegimeAlerter


class TestCheckRegimeChange:
    def setup_method(self):
        self.alerter = RegimeAlerter()

    def test_regime_changed(self):
        alert = self.alerter.check_regime_change(
            instrument="BTC-USD",
            new_regime={"regime_type": "volatile", "confidence": 0.85},
            previous_regime={"regime_type": "trending_up"},
            favored_strategies=["s1", "s2"],
            unfavored_strategies=["s3"],
        )
        assert alert is not None
        assert alert["previous_regime"] == "trending_up"
        assert alert["new_regime"] == "volatile"
        assert alert["confidence"] == 0.85
        assert len(alert["favored_strategies"]) == 2

    def test_no_change(self):
        alert = self.alerter.check_regime_change(
            instrument="BTC-USD",
            new_regime={"regime_type": "trending_up", "confidence": 0.9},
            previous_regime={"regime_type": "trending_up"},
        )
        assert alert is None

    def test_first_detection(self):
        alert = self.alerter.check_regime_change(
            instrument="BTC-USD",
            new_regime={"regime_type": "ranging", "confidence": 0.7},
            previous_regime=None,
        )
        assert alert is not None
        assert alert["previous_regime"] == "unknown"
        assert alert["new_regime"] == "ranging"

    def test_stores_with_db(self):
        conn = mock.Mock()
        cur = mock.Mock()
        conn.cursor.return_value.__enter__ = mock.Mock(return_value=cur)
        conn.cursor.return_value.__exit__ = mock.Mock(return_value=False)

        alerter = RegimeAlerter(db_connection=conn)
        alert = alerter.check_regime_change(
            instrument="BTC-USD",
            new_regime={"regime_type": "volatile", "confidence": 0.8},
            previous_regime={"regime_type": "quiet"},
        )
        assert alert is not None
        # Should call execute for both _store_alert and _log_adaptation_event
        assert cur.execute.call_count == 2
        assert conn.commit.call_count == 2

    def test_empty_favored(self):
        alert = self.alerter.check_regime_change(
            instrument="ETH-USD",
            new_regime={"regime_type": "quiet", "confidence": 0.6},
            previous_regime={"regime_type": "volatile"},
        )
        assert alert["favored_strategies"] == []
        assert alert["unfavored_strategies"] == []


class TestGetRecentAlerts:
    def test_no_connection(self):
        alerter = RegimeAlerter()
        assert alerter.get_recent_alerts() == []

    def test_acknowledge_no_connection(self):
        alerter = RegimeAlerter()
        assert alerter.acknowledge_alert("alert-1") is False
