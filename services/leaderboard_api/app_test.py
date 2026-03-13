"""Tests for the Trading Leaderboard REST API."""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.leaderboard_api.app import (
    Period,
    SortMetric,
    _snapshot_to_dict,
    create_app,
)


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


def _make_snapshot_row(
    user_id=None,
    display_name="Trader A",
    strategy_type="momentum",
    asset_class="crypto",
    period="monthly",
    total_return_pct=0.25,
    sharpe_ratio=1.8,
    win_rate=0.62,
    consistency_score=0.75,
    total_trades=150,
    winning_trades=93,
    losing_trades=57,
    rank=1,
    percentile=0.95,
    snapshot_date=None,
):
    return FakeRecord(
        user_id=user_id or uuid.uuid4(),
        display_name=display_name,
        strategy_type=strategy_type,
        asset_class=asset_class,
        period=period,
        total_return_pct=total_return_pct,
        sharpe_ratio=sharpe_ratio,
        win_rate=win_rate,
        consistency_score=consistency_score,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        rank=rank,
        percentile=percentile,
        snapshot_date=snapshot_date or date(2026, 3, 13),
    )


# --- Snapshot dict conversion ---


class TestSnapshotToDict:
    def test_converts_all_fields(self):
        uid = uuid.uuid4()
        row = _make_snapshot_row(user_id=uid, display_name="Alpha")
        result = _snapshot_to_dict(row)
        assert result["user_id"] == str(uid)
        assert result["display_name"] == "Alpha"
        assert result["total_return_pct"] == 0.25
        assert result["sharpe_ratio"] == 1.8
        assert result["win_rate"] == 0.62
        assert result["consistency_score"] == 0.75
        assert result["total_trades"] == 150
        assert result["winning_trades"] == 93
        assert result["losing_trades"] == 57
        assert result["rank"] == 1
        assert result["percentile"] == 0.95
        assert result["snapshot_date"] == "2026-03-13"

    def test_handles_none_values(self):
        row = _make_snapshot_row(
            sharpe_ratio=None,
            win_rate=None,
            consistency_score=None,
            rank=None,
            percentile=None,
        )
        result = _snapshot_to_dict(row)
        assert result["sharpe_ratio"] is None
        assert result["win_rate"] is None
        assert result["consistency_score"] is None
        assert result["rank"] is None
        assert result["percentile"] is None


# --- GET /leaderboard ---


class TestGetLeaderboard:
    def test_returns_ranked_list(self, client):
        tc, conn = client
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        conn.fetch.return_value = [
            _make_snapshot_row(user_id=id1, display_name="Alpha", rank=1),
            _make_snapshot_row(user_id=id2, display_name="Beta", rank=2),
        ]
        conn.fetchval.return_value = 2

        resp = tc.get("/leaderboard?period=monthly&sort_by=total_return_pct")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["data"][0]["attributes"]["display_name"] == "Alpha"
        assert body["data"][0]["attributes"]["rank"] == 1
        assert body["data"][1]["attributes"]["rank"] == 2
        assert body["meta"]["total"] == 2

    def test_empty_leaderboard(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/leaderboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0

    def test_all_periods(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        for period in ["daily", "weekly", "monthly", "all_time"]:
            resp = tc.get(f"/leaderboard?period={period}")
            assert resp.status_code == 200

    def test_invalid_period(self, client):
        tc, conn = client
        resp = tc.get("/leaderboard?period=invalid")
        assert resp.status_code == 422

    def test_all_sort_metrics(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        for metric in [
            "total_return_pct",
            "sharpe_ratio",
            "win_rate",
            "consistency_score",
        ]:
            resp = tc.get(f"/leaderboard?sort_by={metric}")
            assert resp.status_code == 200

    def test_invalid_sort_metric(self, client):
        tc, conn = client
        resp = tc.get("/leaderboard?sort_by=invalid")
        assert resp.status_code == 422

    def test_filter_by_strategy_type(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            _make_snapshot_row(strategy_type="momentum"),
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/leaderboard?strategy_type=momentum")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1

    def test_filter_by_asset_class(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            _make_snapshot_row(asset_class="crypto"),
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/leaderboard?asset_class=crypto")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1

    def test_combined_filters(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get(
            "/leaderboard?strategy_type=momentum&asset_class=crypto&period=weekly"
        )
        assert resp.status_code == 200

    def test_pagination(self, client):
        tc, conn = client
        conn.fetch.return_value = [_make_snapshot_row(rank=2)]
        conn.fetchval.return_value = 10

        resp = tc.get("/leaderboard?limit=1&offset=1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["limit"] == 1
        assert body["meta"]["offset"] == 1
        assert body["meta"]["total"] == 10


# --- Caching ---


class TestCaching:
    def test_caches_leaderboard_response(self, client):
        tc, conn = client
        conn.fetch.return_value = [_make_snapshot_row()]
        conn.fetchval.return_value = 1

        resp1 = tc.get("/leaderboard?period=daily&sort_by=sharpe_ratio")
        resp2 = tc.get("/leaderboard?period=daily&sort_by=sharpe_ratio")
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # fetch called once for data, fetchval once for count — only on first call
        assert conn.fetch.call_count == 1

    def test_different_params_not_cached(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        tc.get("/leaderboard?period=daily")
        tc.get("/leaderboard?period=weekly")
        assert conn.fetch.call_count == 2


# --- GET /leaderboard/me ---


class TestGetMyRanking:
    def test_returns_user_ranking(self, client):
        tc, conn = client
        uid = uuid.uuid4()
        conn.fetchrow.return_value = _make_snapshot_row(
            user_id=uid, display_name="Me", rank=5, percentile=0.80
        )

        resp = tc.get(
            "/leaderboard/me?period=monthly",
            headers={"X-User-Id": str(uid)},
        )
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["display_name"] == "Me"
        assert attrs["rank"] == 5
        assert attrs["percentile"] == 0.80
        assert body["data"]["id"] == str(uid)

    def test_missing_user_id_header(self, client):
        tc, conn = client
        resp = tc.get("/leaderboard/me?period=monthly")
        assert resp.status_code == 401

    def test_user_not_found(self, client):
        tc, conn = client
        uid = uuid.uuid4()
        conn.fetchrow.return_value = None

        resp = tc.get(
            "/leaderboard/me",
            headers={"X-User-Id": str(uid)},
        )
        assert resp.status_code == 404

    def test_all_periods(self, client):
        tc, conn = client
        uid = uuid.uuid4()
        conn.fetchrow.return_value = _make_snapshot_row(user_id=uid)

        for period in ["daily", "weekly", "monthly", "all_time"]:
            resp = tc.get(
                f"/leaderboard/me?period={period}",
                headers={"X-User-Id": str(uid)},
            )
            assert resp.status_code == 200


# --- PUT /leaderboard/visibility ---


class TestUpdateVisibility:
    def test_opt_in(self, client):
        tc, conn = client
        uid = uuid.uuid4()
        conn.execute.return_value = "UPDATE 1"

        resp = tc.put(
            "/leaderboard/visibility?visible=true",
            headers={"X-User-Id": str(uid)},
        )
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["leaderboard_visible"] is True
        assert attrs["user_id"] == str(uid)

    def test_opt_out(self, client):
        tc, conn = client
        uid = uuid.uuid4()
        conn.execute.return_value = "UPDATE 1"

        resp = tc.put(
            "/leaderboard/visibility?visible=false",
            headers={"X-User-Id": str(uid)},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["leaderboard_visible"] is False

    def test_missing_user_id(self, client):
        tc, conn = client
        resp = tc.put("/leaderboard/visibility?visible=true")
        assert resp.status_code == 401

    def test_user_not_found(self, client):
        tc, conn = client
        uid = uuid.uuid4()
        conn.execute.return_value = "UPDATE 0"

        resp = tc.put(
            "/leaderboard/visibility?visible=true",
            headers={"X-User-Id": str(uid)},
        )
        assert resp.status_code == 404


# --- Health endpoint ---


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
