"""Tests for the Tax Lots REST API."""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.tax_lots.app import create_app
from services.tax_lots.methods import dispose_fifo, dispose_lifo, dispose_specific


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
    # Support transaction context manager
    tx_ctx = AsyncMock()
    tx_ctx.__aenter__ = AsyncMock(return_value=None)
    tx_ctx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction.return_value = tx_ctx
    return pool, conn


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


# ---- Health ----


class TestHealth:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


# ---- GET /lots/{symbol} ----


class TestGetLots:
    def test_get_lots_found(self, client):
        tc, conn = client
        lot_id = str(uuid.uuid4())
        conn.fetch.return_value = [
            FakeRecord(
                lot_id=lot_id,
                symbol="BTC/USD",
                quantity=1.0,
                cost_basis=50000.0,
                acquisition_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
                remaining_quantity=0.5,
                created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
            )
        ]

        resp = tc.get("/lots/BTC%2FUSD")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["symbol"] == "BTC/USD"

    def test_get_lots_not_found(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/lots/DOGE%2FUSD")
        assert resp.status_code == 404


# ---- POST /lots ----


class TestAddLot:
    def test_add_lot(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            lot_id=str(uuid.uuid4()),
            symbol="ETH/USD",
            quantity=10.0,
            cost_basis=3000.0,
            acquisition_date=datetime(2025, 7, 1, tzinfo=timezone.utc),
            remaining_quantity=10.0,
            created_at=datetime(2025, 7, 1, tzinfo=timezone.utc),
        )

        resp = tc.post(
            "/lots",
            json={
                "symbol": "ETH/USD",
                "quantity": 10.0,
                "cost_basis": 3000.0,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["symbol"] == "ETH/USD"


# ---- POST /dispose ----


class TestDispose:
    def test_dispose_fifo(self, client):
        tc, conn = client
        lot1_id = str(uuid.uuid4())
        lot2_id = str(uuid.uuid4())

        conn.fetch.return_value = [
            FakeRecord(
                lot_id=lot1_id,
                symbol="BTC/USD",
                quantity=1.0,
                cost_basis=40000.0,
                acquisition_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
                remaining_quantity=1.0,
            ),
            FakeRecord(
                lot_id=lot2_id,
                symbol="BTC/USD",
                quantity=1.0,
                cost_basis=50000.0,
                acquisition_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
                remaining_quantity=1.0,
            ),
        ]

        resp = tc.post(
            "/dispose",
            json={
                "symbol": "BTC/USD",
                "quantity": 1.5,
                "sale_price": 60000.0,
                "method": "FIFO",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        disposals = body["data"]["attributes"]["disposals"]
        assert len(disposals) == 2
        # FIFO: first lot fully consumed, second partially
        assert disposals[0]["lot_id"] == lot1_id
        assert disposals[0]["quantity_disposed"] == 1.0
        assert disposals[1]["lot_id"] == lot2_id
        assert disposals[1]["quantity_disposed"] == 0.5
        # Gains: (60000 - 40000) * 1.0 + (60000 - 50000) * 0.5 = 25000
        assert body["data"]["attributes"]["total_realized_gain"] == 25000.0

    def test_dispose_lifo(self, client):
        tc, conn = client
        lot1_id = str(uuid.uuid4())
        lot2_id = str(uuid.uuid4())

        conn.fetch.return_value = [
            FakeRecord(
                lot_id=lot1_id,
                symbol="BTC/USD",
                quantity=1.0,
                cost_basis=40000.0,
                acquisition_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
                remaining_quantity=1.0,
            ),
            FakeRecord(
                lot_id=lot2_id,
                symbol="BTC/USD",
                quantity=1.0,
                cost_basis=50000.0,
                acquisition_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
                remaining_quantity=1.0,
            ),
        ]

        resp = tc.post(
            "/dispose",
            json={
                "symbol": "BTC/USD",
                "quantity": 1.0,
                "sale_price": 60000.0,
                "method": "LIFO",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        disposals = body["data"]["attributes"]["disposals"]
        # LIFO: second lot consumed first
        assert disposals[0]["lot_id"] == lot2_id
        assert disposals[0]["realized_gain"] == 10000.0

    def test_dispose_specific_id(self, client):
        tc, conn = client
        lot_id = str(uuid.uuid4())

        conn.fetch.return_value = [
            FakeRecord(
                lot_id=lot_id,
                symbol="ETH/USD",
                quantity=5.0,
                cost_basis=3000.0,
                acquisition_date=datetime(2025, 3, 1, tzinfo=timezone.utc),
                remaining_quantity=5.0,
            ),
        ]

        resp = tc.post(
            "/dispose",
            json={
                "symbol": "ETH/USD",
                "quantity": 2.0,
                "sale_price": 4000.0,
                "method": "SPECIFIC_ID",
                "lot_id": lot_id,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        disposals = body["data"]["attributes"]["disposals"]
        assert len(disposals) == 1
        assert disposals[0]["lot_id"] == lot_id
        assert disposals[0]["realized_gain"] == 2000.0

    def test_dispose_specific_id_missing_lot_id(self, client):
        tc, conn = client
        resp = tc.post(
            "/dispose",
            json={
                "symbol": "BTC/USD",
                "quantity": 1.0,
                "sale_price": 60000.0,
                "method": "SPECIFIC_ID",
            },
        )
        assert resp.status_code == 422

    def test_dispose_no_lots(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.post(
            "/dispose",
            json={
                "symbol": "UNKNOWN/USD",
                "quantity": 1.0,
                "sale_price": 100.0,
                "method": "FIFO",
            },
        )
        assert resp.status_code == 404

    def test_dispose_insufficient_quantity(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                lot_id=str(uuid.uuid4()),
                symbol="BTC/USD",
                quantity=1.0,
                cost_basis=50000.0,
                acquisition_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
                remaining_quantity=0.5,
            ),
        ]

        resp = tc.post(
            "/dispose",
            json={
                "symbol": "BTC/USD",
                "quantity": 1.0,
                "sale_price": 60000.0,
                "method": "FIFO",
            },
        )
        assert resp.status_code == 422


# ---- GET /gains ----


class TestGetGains:
    def test_get_all_gains(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                gain_id=str(uuid.uuid4()),
                lot_id=str(uuid.uuid4()),
                symbol="BTC/USD",
                quantity_disposed=1.0,
                cost_basis=40000.0,
                sale_price=60000.0,
                realized_gain=20000.0,
                acquisition_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
                disposal_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
                holding_period="LONG_TERM",
            )
        ]

        resp = tc.get("/gains")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["count"] == 1
        assert attrs["total_realized_gain"] == 20000.0

    def test_get_gains_filtered(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/gains?symbol=ETH%2FUSD&holding_period=SHORT_TERM")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["count"] == 0


# ---- Unit tests for disposal methods ----


class TestDisposalMethods:
    def _make_lots(self):
        return [
            {
                "lot_id": "lot-1",
                "symbol": "BTC/USD",
                "quantity": 2.0,
                "cost_basis": 30000.0,
                "acquisition_date": datetime(2024, 1, 15, tzinfo=timezone.utc),
                "remaining_quantity": 2.0,
            },
            {
                "lot_id": "lot-2",
                "symbol": "BTC/USD",
                "quantity": 3.0,
                "cost_basis": 40000.0,
                "acquisition_date": datetime(2024, 6, 15, tzinfo=timezone.utc),
                "remaining_quantity": 3.0,
            },
            {
                "lot_id": "lot-3",
                "symbol": "BTC/USD",
                "quantity": 1.0,
                "cost_basis": 50000.0,
                "acquisition_date": datetime(2025, 3, 1, tzinfo=timezone.utc),
                "remaining_quantity": 1.0,
            },
        ]

    def test_fifo_multi_lot(self):
        lots = self._make_lots()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        gains, updates = dispose_fifo(lots, 4.0, 55000.0, now)

        assert len(gains) == 2
        # First lot fully consumed
        assert gains[0].lot_id == "lot-1"
        assert gains[0].quantity_disposed == 2.0
        assert gains[0].realized_gain == (55000.0 - 30000.0) * 2.0
        assert gains[0].holding_period == "LONG_TERM"
        # Second lot partially consumed
        assert gains[1].lot_id == "lot-2"
        assert gains[1].quantity_disposed == 2.0
        assert gains[1].realized_gain == (55000.0 - 40000.0) * 2.0
        assert gains[1].holding_period == "LONG_TERM"

        assert updates[0]["remaining_quantity"] == 0.0
        assert updates[1]["remaining_quantity"] == 1.0

    def test_lifo_multi_lot(self):
        lots = self._make_lots()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        gains, updates = dispose_lifo(lots, 3.0, 55000.0, now)

        assert len(gains) == 2
        # LIFO: lot-3 first, then lot-2
        assert gains[0].lot_id == "lot-3"
        assert gains[0].quantity_disposed == 1.0
        assert gains[0].holding_period == "SHORT_TERM"
        assert gains[1].lot_id == "lot-2"
        assert gains[1].quantity_disposed == 2.0

    def test_specific_id(self):
        lots = self._make_lots()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        gains, updates = dispose_specific(lots, "lot-2", 1.5, 55000.0, now)

        assert len(gains) == 1
        assert gains[0].lot_id == "lot-2"
        assert gains[0].quantity_disposed == 1.5
        assert updates[0]["remaining_quantity"] == 1.5

    def test_specific_id_not_found(self):
        lots = self._make_lots()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="not found"):
            dispose_specific(lots, "nonexistent", 1.0, 55000.0, now)

    def test_insufficient_quantity_raises(self):
        lots = self._make_lots()
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="Insufficient"):
            dispose_fifo(lots, 100.0, 55000.0, now)

    def test_holding_period_boundary(self):
        """Exactly 365 days is still SHORT_TERM, 366 is LONG_TERM."""
        lot = [
            {
                "lot_id": "lot-boundary",
                "symbol": "X",
                "quantity": 1.0,
                "cost_basis": 100.0,
                "acquisition_date": datetime(2025, 3, 1, tzinfo=timezone.utc),
                "remaining_quantity": 1.0,
            }
        ]
        # 365 days later
        short = datetime(2025, 3, 1, tzinfo=timezone.utc) + timedelta(days=365)
        gains_s, _ = dispose_fifo(lot, 1.0, 200.0, short)
        assert gains_s[0].holding_period == "SHORT_TERM"

        lot[0]["remaining_quantity"] = 1.0  # reset
        long = datetime(2025, 3, 1, tzinfo=timezone.utc) + timedelta(days=366)
        gains_l, _ = dispose_fifo(lot, 1.0, 200.0, long)
        assert gains_l[0].holding_period == "LONG_TERM"
