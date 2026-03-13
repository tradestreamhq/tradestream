"""Tests for the Trade Journal REST API."""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.trade_journal_api.app import create_app


class FakeRecord(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


_ENTRY_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
_TRADE_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")
_NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


def _sample_row(**overrides):
    defaults = dict(
        id=_ENTRY_ID,
        trade_id=_TRADE_ID,
        entry_notes="Looked like a breakout",
        exit_notes="Closed at resistance",
        emotion_tag="confident",
        lesson_learned="Wait for confirmation",
        rating=4,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return FakeRecord(**defaults)


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestCreateEntry:
    def test_create_full(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _sample_row()
        conn.executemany.return_value = None

        resp = tc.post(
            "/entries",
            json={
                "trade_id": str(_TRADE_ID),
                "entry_notes": "Looked like a breakout",
                "exit_notes": "Closed at resistance",
                "emotion_tag": "confident",
                "lesson_learned": "Wait for confirmation",
                "rating": 4,
                "tags": ["breakout", "crypto"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["type"] == "journal_entry"
        attrs = body["data"]["attributes"]
        assert attrs["emotion_tag"] == "confident"
        assert attrs["rating"] == 4
        assert attrs["tags"] == ["breakout", "crypto"]

    def test_create_minimal(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _sample_row(
            trade_id=None,
            entry_notes="",
            exit_notes="",
            emotion_tag=None,
            lesson_learned="",
            rating=None,
        )

        resp = tc.post("/entries", json={})
        assert resp.status_code == 200

    def test_create_invalid_emotion(self, client):
        tc, _ = client
        resp = tc.post("/entries", json={"emotion_tag": "happy"})
        assert resp.status_code == 422

    def test_create_invalid_rating(self, client):
        tc, _ = client
        resp = tc.post("/entries", json={"rating": 6})
        assert resp.status_code == 422


class TestListEntries:
    def test_list_all(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        conn.fetch.side_effect = [
            [_sample_row()],
            [FakeRecord(tag="breakout")],
        ]

        resp = tc.get("/entries")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["tags"] == ["breakout"]

    def test_filter_by_emotion(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        conn.fetch.side_effect = [
            [_sample_row()],
            [FakeRecord(tag="breakout")],
        ]

        resp = tc.get("/entries?emotion=confident")
        assert resp.status_code == 200

    def test_filter_by_rating(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.side_effect = [[]]

        resp = tc.get("/entries?rating=5")
        assert resp.status_code == 200
        assert resp.json()["meta"]["total"] == 0

    def test_filter_by_tag(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        conn.fetch.side_effect = [
            [_sample_row()],
            [FakeRecord(tag="breakout")],
        ]

        resp = tc.get("/entries?tag=breakout")
        assert resp.status_code == 200

    def test_filter_by_date_range(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.side_effect = [[]]

        resp = tc.get(
            "/entries?date_from=2026-01-01T00:00:00Z&date_to=2026-12-31T23:59:59Z"
        )
        assert resp.status_code == 200


class TestGetEntry:
    def test_get_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _sample_row()
        conn.fetch.return_value = [
            FakeRecord(tag="breakout"),
            FakeRecord(tag="crypto"),
        ]

        resp = tc.get(f"/entries/{_ENTRY_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == str(_ENTRY_ID)
        assert set(body["data"]["attributes"]["tags"]) == {"breakout", "crypto"}

    def test_get_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/entries/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestUpdateEntry:
    def test_update_notes_and_tags(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(id=_ENTRY_ID),
            _sample_row(entry_notes="Updated notes"),
        ]
        conn.execute.return_value = None
        conn.executemany.return_value = None

        resp = tc.put(
            f"/entries/{_ENTRY_ID}",
            json={
                "entry_notes": "Updated notes",
                "tags": ["reversal", "mistake"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["tags"] == ["reversal", "mistake"]

    def test_update_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.put(
            f"/entries/{uuid.uuid4()}",
            json={"entry_notes": "test"},
        )
        assert resp.status_code == 404

    def test_update_emotion_and_rating(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(id=_ENTRY_ID),
            _sample_row(emotion_tag="fearful", rating=2),
        ]
        conn.fetch.return_value = [FakeRecord(tag="breakout")]

        resp = tc.put(
            f"/entries/{_ENTRY_ID}",
            json={"emotion_tag": "fearful", "rating": 2},
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["emotion_tag"] == "fearful"
        assert attrs["rating"] == 2

    def test_update_lesson_learned(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(id=_ENTRY_ID),
            _sample_row(lesson_learned="Don't chase"),
        ]
        conn.fetch.return_value = []

        resp = tc.put(
            f"/entries/{_ENTRY_ID}",
            json={"lesson_learned": "Don't chase"},
        )
        assert resp.status_code == 200
        assert (
            resp.json()["data"]["attributes"]["lesson_learned"] == "Don't chase"
        )


class TestStats:
    def test_stats_full(self, client):
        tc, conn = client
        conn.fetch.side_effect = [
            [
                FakeRecord(
                    emotion_tag="confident",
                    total_trades=10,
                    wins=7,
                    losses=3,
                    avg_pnl=150.0,
                    total_pnl=1500.0,
                ),
                FakeRecord(
                    emotion_tag="fearful",
                    total_trades=5,
                    wins=1,
                    losses=4,
                    avg_pnl=-100.0,
                    total_pnl=-500.0,
                ),
            ],
            [
                FakeRecord(
                    rating=4, total_trades=8, avg_pnl=200.0, total_pnl=1600.0
                ),
                FakeRecord(
                    rating=2, total_trades=3, avg_pnl=-50.0, total_pnl=-150.0
                ),
            ],
            [
                FakeRecord(tag="fomo", occurrences=5, avg_pnl=-200.0),
                FakeRecord(tag="no-stop-loss", occurrences=3, avg_pnl=-350.0),
            ],
        ]

        resp = tc.get("/stats")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]

        assert len(attrs["win_rate_by_emotion"]) == 2
        confident = attrs["win_rate_by_emotion"][0]
        assert confident["emotion_tag"] == "confident"
        assert confident["win_rate"] == 0.7

        assert len(attrs["avg_pnl_by_rating"]) == 2
        assert attrs["avg_pnl_by_rating"][0]["rating"] == 4
        assert attrs["avg_pnl_by_rating"][0]["avg_pnl"] == 200.0

        assert len(attrs["common_mistakes"]) == 2
        assert attrs["common_mistakes"][0]["tag"] == "fomo"

    def test_stats_empty(self, client):
        tc, conn = client
        conn.fetch.side_effect = [[], [], []]

        resp = tc.get("/stats")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["win_rate_by_emotion"] == []
        assert attrs["avg_pnl_by_rating"] == []
        assert attrs["common_mistakes"] == []


class TestStreaks:
    def test_streaks_with_data(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                trade_id=uuid.uuid4(),
                symbol="BTC/USD",
                pnl=100.0,
                closed_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
                emotion_tag="confident",
                rating=4,
            ),
            FakeRecord(
                trade_id=uuid.uuid4(),
                symbol="ETH/USD",
                pnl=50.0,
                closed_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                emotion_tag="neutral",
                rating=3,
            ),
            FakeRecord(
                trade_id=uuid.uuid4(),
                symbol="BTC/USD",
                pnl=-80.0,
                closed_at=datetime(2026, 3, 3, tzinfo=timezone.utc),
                emotion_tag="fearful",
                rating=2,
            ),
        ]

        resp = tc.get("/streaks")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]

        assert attrs["current_streak"]["type"] == "losing"
        assert attrs["current_streak"]["length"] == 1
        assert attrs["longest_winning_streak"]["length"] == 2
        assert attrs["longest_losing_streak"]["length"] == 1

    def test_streaks_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/streaks")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["current_streak"]["type"] == "none"
        assert attrs["longest_winning_streak"]["length"] == 0

    def test_streaks_all_wins(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                trade_id=uuid.uuid4(),
                symbol="BTC/USD",
                pnl=100.0,
                closed_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
                emotion_tag="confident",
                rating=5,
            ),
            FakeRecord(
                trade_id=uuid.uuid4(),
                symbol="ETH/USD",
                pnl=200.0,
                closed_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
                emotion_tag="confident",
                rating=5,
            ),
        ]

        resp = tc.get("/streaks")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["current_streak"]["type"] == "winning"
        assert attrs["current_streak"]["length"] == 2
        assert attrs["longest_losing_streak"]["length"] == 0


class TestCalendar:
    def test_calendar_data(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                date=date(2026, 3, 1),
                trade_count=3,
                wins=2,
                losses=1,
                daily_pnl=500.0,
            ),
            FakeRecord(
                date=date(2026, 3, 2),
                trade_count=1,
                wins=0,
                losses=1,
                daily_pnl=-200.0,
            ),
        ]

        resp = tc.get("/calendar")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        day1 = body["data"][0]["attributes"]
        assert day1["date"] == "2026-03-01"
        assert day1["daily_pnl"] == 500.0
        assert day1["wins"] == 2

    def test_calendar_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/calendar")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 0

    def test_calendar_with_date_filter(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                date=date(2026, 3, 1),
                trade_count=1,
                wins=1,
                losses=0,
                daily_pnl=100.0,
            ),
        ]

        resp = tc.get(
            "/calendar?date_from=2026-03-01T00:00:00Z"
            "&date_to=2026-03-31T23:59:59Z"
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1
