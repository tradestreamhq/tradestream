"""Tests for the Risk Management REST API."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from services.risk_management_api.app import create_app


class FakeRecord(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


def _make_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


# =================================================================
# Health
# =================================================================


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


# =================================================================
# POST /calculate
# =================================================================


class TestCalculatePositionSize:
    def test_basic_calculation(self, client):
        tc, _ = client
        resp = tc.post(
            "/calculate",
            json={
                "account_size": 100000,
                "risk_pct": 0.02,
                "entry_price": 50.0,
                "stop_price": 48.0,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        # $100k * 2% = $2000 risk, $2000 / $2 spread = 1000 shares
        assert attrs["dollar_risk"] == 2000.0
        assert attrs["position_size"] == 1000.0
        assert attrs["position_value"] == 50000.0

    def test_short_position(self, client):
        tc, _ = client
        resp = tc.post(
            "/calculate",
            json={
                "account_size": 50000,
                "risk_pct": 0.01,
                "entry_price": 100.0,
                "stop_price": 105.0,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        # $50k * 1% = $500 risk, $500 / $5 spread = 100 shares
        assert attrs["dollar_risk"] == 500.0
        assert attrs["position_size"] == 100.0

    def test_equal_prices_rejected(self, client):
        tc, _ = client
        resp = tc.post(
            "/calculate",
            json={
                "account_size": 100000,
                "risk_pct": 0.02,
                "entry_price": 50.0,
                "stop_price": 50.0,
            },
        )
        assert resp.status_code == 422
        assert "VALIDATION_ERROR" in resp.json()["error"]["code"]

    def test_missing_fields_rejected(self, client):
        tc, _ = client
        resp = tc.post("/calculate", json={"account_size": 100000})
        assert resp.status_code == 422

    def test_negative_account_rejected(self, client):
        tc, _ = client
        resp = tc.post(
            "/calculate",
            json={
                "account_size": -100,
                "risk_pct": 0.02,
                "entry_price": 50.0,
                "stop_price": 48.0,
            },
        )
        assert resp.status_code == 422


# =================================================================
# GET /limits
# =================================================================


class TestGetRiskLimits:
    def test_get_limits(self, client):
        tc, conn = client
        limit_id = uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=limit_id,
            max_position_size=Decimal("10000"),
            max_position_pct=Decimal("0.05"),
            max_daily_loss=Decimal("1000"),
            max_daily_loss_pct=Decimal("0.02"),
            max_drawdown_pct=Decimal("0.10"),
            max_open_positions=20,
            max_sector_exposure_pct=Decimal("0.30"),
            max_correlated_exposure_pct=Decimal("0.40"),
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        resp = tc.get("/limits")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["max_position_size"] == 10000.0
        assert attrs["max_daily_loss_pct"] == 0.02
        assert attrs["max_open_positions"] == 20

    def test_limits_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.get("/limits")
        assert resp.status_code == 404


# =================================================================
# PUT /limits
# =================================================================


class TestUpdateRiskLimits:
    def test_update_single_field(self, client):
        tc, conn = client
        limit_id = uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=limit_id,
            max_position_size=Decimal("20000"),
            max_position_pct=Decimal("0.05"),
            max_daily_loss=Decimal("1000"),
            max_daily_loss_pct=Decimal("0.02"),
            max_drawdown_pct=Decimal("0.10"),
            max_open_positions=20,
            max_sector_exposure_pct=Decimal("0.30"),
            max_correlated_exposure_pct=Decimal("0.40"),
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 3, 13, tzinfo=timezone.utc),
        )

        resp = tc.put("/limits", json={"max_position_size": 20000})
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["max_position_size"] == 20000.0

    def test_update_multiple_fields(self, client):
        tc, conn = client
        limit_id = uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=limit_id,
            max_position_size=Decimal("15000"),
            max_position_pct=Decimal("0.08"),
            max_daily_loss=Decimal("2000"),
            max_daily_loss_pct=Decimal("0.03"),
            max_drawdown_pct=Decimal("0.15"),
            max_open_positions=30,
            max_sector_exposure_pct=Decimal("0.30"),
            max_correlated_exposure_pct=Decimal("0.40"),
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 3, 13, tzinfo=timezone.utc),
        )

        resp = tc.put(
            "/limits",
            json={
                "max_position_size": 15000,
                "max_daily_loss": 2000,
                "max_drawdown_pct": 0.15,
                "max_open_positions": 30,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["max_open_positions"] == 30
        assert attrs["max_drawdown_pct"] == 0.15

    def test_update_empty_body_rejected(self, client):
        tc, conn = client
        resp = tc.put("/limits", json={})
        assert resp.status_code == 422

    def test_update_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        resp = tc.put("/limits", json={"max_position_size": 5000})
        assert resp.status_code == 404


# =================================================================
# GET /exposure
# =================================================================


class TestGetExposure:
    def test_exposure_with_positions(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                symbol="BTC/USD",
                quantity=Decimal("0.5"),
                avg_entry_price=Decimal("60000"),
                unrealized_pnl=Decimal("1000"),
            ),
            FakeRecord(
                symbol="ETH/USD",
                quantity=Decimal("10"),
                avg_entry_price=Decimal("3000"),
                unrealized_pnl=Decimal("500"),
            ),
        ]

        resp = tc.get("/exposure")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["position_count"] == 2
        # BTC: 0.5 * 60000 = 30000, ETH: 10 * 3000 = 30000
        assert attrs["total_exposure"] == 60000.0
        assert len(attrs["positions"]) == 2
        assert "by_asset_class" in attrs
        assert "by_sector" in attrs
        assert "correlated_groups" in attrs

    def test_exposure_empty_portfolio(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/exposure")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["position_count"] == 0
        assert attrs["total_exposure"] == 0.0


# =================================================================
# POST /check — Risk check middleware
# =================================================================


class TestCheckTradeRisk:
    def _default_limits(self):
        return FakeRecord(
            id=uuid4(),
            max_position_size=Decimal("10000"),
            max_position_pct=Decimal("0.05"),
            max_daily_loss=Decimal("1000"),
            max_daily_loss_pct=Decimal("0.02"),
            max_drawdown_pct=Decimal("0.10"),
            max_open_positions=20,
            max_sector_exposure_pct=Decimal("0.30"),
            max_correlated_exposure_pct=Decimal("0.40"),
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    def test_approved_buy(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            self._default_limits(),  # risk_limits
            FakeRecord(today_loss=Decimal("0")),  # today's loss
        ]
        conn.fetchval.return_value = 5  # open positions

        resp = tc.post(
            "/check",
            json={
                "instrument": "BTC/USD",
                "side": "BUY",
                "size": 0.1,
                "entry_price": 60000,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["approved"] is True
        assert len(attrs["errors"]) == 0

    def test_rejected_exceeds_position_size(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            self._default_limits(),  # max_position_size = 10000
            FakeRecord(today_loss=Decimal("0")),
        ]
        conn.fetchval.return_value = 5

        resp = tc.post(
            "/check",
            json={
                "instrument": "BTC/USD",
                "side": "BUY",
                "size": 1.0,
                "entry_price": 60000,  # value = 60000 > 10000
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["approved"] is False
        assert any("max position" in e.lower() for e in attrs["errors"])

    def test_rejected_daily_loss_reached(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            self._default_limits(),  # max_daily_loss = 1000
            FakeRecord(today_loss=Decimal("-1500")),  # already lost $1500
        ]
        conn.fetchval.return_value = 5

        resp = tc.post(
            "/check",
            json={
                "instrument": "ETH/USD",
                "side": "BUY",
                "size": 1.0,
                "entry_price": 3000,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["approved"] is False
        assert any("daily loss" in e.lower() for e in attrs["errors"])

    def test_rejected_max_positions_reached(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            self._default_limits(),  # max_open_positions = 20
            FakeRecord(today_loss=Decimal("0")),
        ]
        conn.fetchval.return_value = 20  # already at max

        resp = tc.post(
            "/check",
            json={
                "instrument": "SOL/USD",
                "side": "BUY",
                "size": 10.0,
                "entry_price": 100,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["approved"] is False
        assert any("max open positions" in e.lower() for e in attrs["errors"])

    def test_sell_insufficient_position(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            self._default_limits(),
            FakeRecord(today_loss=Decimal("0")),
            FakeRecord(quantity=Decimal("0.01")),  # only 0.01 held
        ]
        conn.fetchval.return_value = 5

        resp = tc.post(
            "/check",
            json={
                "instrument": "BTC/USD",
                "side": "SELL",
                "size": 1.0,
                "entry_price": 60000,
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["approved"] is False
        assert any("insufficient" in e.lower() for e in attrs["errors"])

    def test_risk_warning_with_stop(self, client):
        tc, conn = client
        # Daily loss budget: max_daily_loss=1000, today_loss=800 → remaining=200
        conn.fetchrow.side_effect = [
            self._default_limits(),
            FakeRecord(today_loss=Decimal("-800")),
        ]
        conn.fetchval.return_value = 5

        resp = tc.post(
            "/check",
            json={
                "instrument": "ETH/USD",
                "side": "BUY",
                "size": 1.0,
                "entry_price": 3000,
                "stop_price": 2700,  # risk = $300 > $200 remaining
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert len(attrs["warnings"]) > 0

    def test_no_limits_configured(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            "/check",
            json={
                "instrument": "BTC/USD",
                "side": "BUY",
                "size": 0.1,
                "entry_price": 60000,
            },
        )
        assert resp.status_code == 500


# =================================================================
# GET /report
# =================================================================


class TestGetRiskReport:
    def test_report(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            # today P&L
            FakeRecord(
                gross_profit=Decimal("500"),
                gross_loss=Decimal("-200"),
                net_pnl=Decimal("300"),
                trades_closed=5,
            ),
            # unrealized
            FakeRecord(total_unrealized=Decimal("1000")),
            # total realized
            FakeRecord(total_realized=Decimal("5000")),
            # peak equity
            FakeRecord(peak_equity=Decimal("6000")),
            # risk limits
            FakeRecord(
                max_daily_loss=Decimal("1000"),
                max_drawdown_pct=Decimal("0.10"),
            ),
        ]
        conn.fetch.return_value = [
            FakeRecord(
                symbol="BTC/USD",
                quantity=Decimal("0.5"),
                avg_entry_price=Decimal("60000"),
                unrealized_pnl=Decimal("1000"),
            )
        ]

        resp = tc.get("/report")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert "pnl" in attrs
        assert attrs["pnl"]["net_pnl"] == 300.0
        assert "equity" in attrs
        assert "drawdown" in attrs
        assert "exposure" in attrs
        assert "limits_utilization" in attrs
        assert attrs["date"] == date.today().isoformat()

    def test_report_empty_portfolio(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(
                gross_profit=Decimal("0"),
                gross_loss=Decimal("0"),
                net_pnl=Decimal("0"),
                trades_closed=0,
            ),
            FakeRecord(total_unrealized=Decimal("0")),
            FakeRecord(total_realized=Decimal("0")),
            FakeRecord(peak_equity=Decimal("0")),
            FakeRecord(
                max_daily_loss=Decimal("1000"),
                max_drawdown_pct=Decimal("0.10"),
            ),
        ]
        conn.fetch.return_value = []

        resp = tc.get("/report")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["exposure"]["total"] == 0.0
        assert attrs["drawdown"]["pct"] == 0.0
