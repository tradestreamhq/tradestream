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
        screenshots_urls=["https://example.com/chart1.png"],
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
            "/",
            json={
                "trade_id": str(_TRADE_ID),
                "entry_notes": "Looked like a breakout",
                "exit_notes": "Closed at resistance",
                "emotion_tag": "confident",
                "lesson_learned": "Wait for confirmation",
                "rating": 4,
                "tags": ["breakout", "crypto"],
                "screenshots_urls": ["https://example.com/chart1.png"],
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["type"] == "journal_entry"
        attrs = body["data"]["attributes"]
        assert attrs["emotion_tag"] == "confident"
        assert attrs["rating"] == 4
        assert attrs["tags"] == ["breakout", "crypto"]
        assert attrs["screenshots_urls"] == ["https://example.com/chart1.png"]

    def test_create_minimal(self, client):
        tc, conn = client
        conn.fetchrow.return_value = _sample_row(
            trade_id=None,
            entry_notes="",
            exit_notes="",
            emotion_tag=None,
            lesson_learned="",
            rating=None,
            screenshots_urls=[],
        )

        resp = tc.post("/", json={})
        assert resp.status_code == 201

    def test_create_invalid_emotion(self, client):
        tc, _ = client
        resp = tc.post("/", json={"emotion_tag": "happy"})
        assert resp.status_code == 422

    def test_create_invalid_rating(self, client):
        tc, _ = client
        resp = tc.post("/", json={"rating": 6})
        assert resp.status_code == 422


class TestListEntries:
    def test_list_all(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        conn.fetch.side_effect = [
            [_sample_row()],
            [FakeRecord(tag="breakout")],
        ]

        resp = tc.get("/")
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

        resp = tc.get("/?emotion=confident")
        assert resp.status_code == 200

    def test_filter_by_rating(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.side_effect = [[]]

        resp = tc.get("/?rating=5")
        assert resp.status_code == 200
        assert resp.json()["meta"]["total"] == 0

    def test_filter_by_tag(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        conn.fetch.side_effect = [
            [_sample_row()],
            [FakeRecord(tag="breakout")],
        ]

        resp = tc.get("/?tag=breakout")
        assert resp.status_code == 200

    def test_filter_by_date_range(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.side_effect = [[]]

        resp = tc.get(
            "/?date_from=2026-01-01T00:00:00Z&date_to=2026-12-31T23:59:59Z"
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

        resp = tc.get(f"/{_ENTRY_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == str(_ENTRY_ID)
        assert set(body["data"]["attributes"]["tags"]) == {"breakout", "crypto"}

    def test_get_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/{uuid.uuid4()}")
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
            f"/{_ENTRY_ID}",
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
            f"/{uuid.uuid4()}",
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
            f"/{_ENTRY_ID}",
            json={"emotion_tag": "fearful", "rating": 2},
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["emotion_tag"] == "fearful"
        assert attrs["rating"] == 2

    def test_update_screenshots(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(id=_ENTRY_ID),
            _sample_row(screenshots_urls=["https://example.com/new.png"]),
        ]
        conn.fetch.return_value = []

        resp = tc.put(
            f"/{_ENTRY_ID}",
            json={"screenshots_urls": ["https://example.com/new.png"]},
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["screenshots_urls"] == ["https://example.com/new.png"]

    def test_update_lesson_learned(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(id=_ENTRY_ID),
            _sample_row(lesson_learned="Don't chase"),
        ]
        conn.fetch.return_value = []

        resp = tc.put(
            f"/{_ENTRY_ID}",
            json={"lesson_learned": "Don't chase"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["lesson_learned"] == "Don't chase"


class TestTags:
    def test_list_tags(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(tag="breakout", entry_count=5),
            FakeRecord(tag="fomo", entry_count=3),
            FakeRecord(tag="reversal", entry_count=1),
        ]

        resp = tc.get("/tags")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 3
        assert body["data"][0]["attributes"]["tag"] == "breakout"
        assert body["data"][0]["attributes"]["entry_count"] == 5

    def test_list_tags_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/tags")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 0


class TestStats:
    def test_stats_full(self, client):
        tc, conn = client
        conn.fetch.side_effect = [
            # streak_rows
            [
                FakeRecord(entry_date=date(2026, 3, 13)),
                FakeRecord(entry_date=date(2026, 3, 12)),
                FakeRecord(entry_date=date(2026, 3, 11)),
                FakeRecord(entry_date=date(2026, 3, 9)),
            ],
            # weekly_rows
            [
                FakeRecord(week_start=date(2026, 3, 9), entry_count=4),
                FakeRecord(week_start=date(2026, 3, 2), entry_count=2),
            ],
            # tag_rows
            [
                FakeRecord(tag="breakout", entry_count=5),
                FakeRecord(tag="fomo", entry_count=3),
            ],
            # emotion_rows
            [
                FakeRecord(
                    emotion_tag="confident",
                    total_trades=10,
                    wins=7,
                    losses=3,
                    avg_pnl=150.0,
                ),
            ],
        ]

        resp = tc.get("/stats")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]

        assert attrs["current_streak"] == 3
        assert attrs["longest_streak"] == 3
        assert len(attrs["entries_per_week"]) == 2
        assert attrs["entries_per_week"][0]["entry_count"] == 4
        assert len(attrs["most_used_tags"]) == 2
        assert attrs["most_used_tags"][0]["tag"] == "breakout"
        assert len(attrs["win_rate_by_emotion"]) == 1
        assert attrs["win_rate_by_emotion"][0]["win_rate"] == 0.7

    def test_stats_empty(self, client):
        tc, conn = client
        conn.fetch.side_effect = [[], [], [], []]

        resp = tc.get("/stats")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["current_streak"] == 0
        assert attrs["longest_streak"] == 0
        assert attrs["entries_per_week"] == []
        assert attrs["most_used_tags"] == []
        assert attrs["win_rate_by_emotion"] == []
