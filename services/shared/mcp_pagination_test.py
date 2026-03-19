"""Tests for MCP pagination utilities."""

import pytest

from services.shared.mcp_pagination import paginated_response, clamp_pagination


class TestPaginatedResponse:
    def test_basic(self):
        items = [{"id": 1}, {"id": 2}]
        resp = paginated_response(items, offset=0, limit=10, total=2)
        assert resp["items"] == items
        assert resp["pagination"]["offset"] == 0
        assert resp["pagination"]["limit"] == 10
        assert resp["pagination"]["total"] == 2
        assert resp["pagination"]["has_more"] is False

    def test_has_more_true(self):
        resp = paginated_response(
            [{"id": i} for i in range(10)], offset=0, limit=10, total=25
        )
        assert resp["pagination"]["has_more"] is True

    def test_last_page(self):
        resp = paginated_response(
            [{"id": 21}], offset=20, limit=10, total=21
        )
        assert resp["pagination"]["has_more"] is False

    def test_empty(self):
        resp = paginated_response([], offset=0, limit=10, total=0)
        assert resp["items"] == []
        assert resp["pagination"]["has_more"] is False


class TestClampPagination:
    def test_valid_values(self):
        offset, limit = clamp_pagination(5, 20)
        assert offset == 5
        assert limit == 20

    def test_negative_offset(self):
        offset, limit = clamp_pagination(-1, 10)
        assert offset == 0

    def test_zero_limit(self):
        offset, limit = clamp_pagination(0, 0)
        assert limit == 1

    def test_exceeds_max_limit(self):
        offset, limit = clamp_pagination(0, 500, max_limit=100)
        assert limit == 100

    def test_custom_max_limit(self):
        offset, limit = clamp_pagination(0, 300, max_limit=200)
        assert limit == 200
