"""Tests for standardized REST API response helpers."""

import json

import pytest

from services.rest_api_shared.responses import (
    collection_response,
    conflict,
    error_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)


class TestSuccessResponse:
    def test_basic_response(self):
        resp = success_response({"name": "test"}, "widget")
        body = json.loads(resp.body)
        assert resp.status_code == 200
        assert body["data"]["type"] == "widget"
        assert body["data"]["attributes"]["name"] == "test"
        assert "id" not in body["data"]

    def test_with_resource_id(self):
        resp = success_response({"x": 1}, "widget", resource_id="abc-123")
        body = json.loads(resp.body)
        assert body["data"]["id"] == "abc-123"

    def test_custom_status_code(self):
        resp = success_response({"x": 1}, "widget", status_code=201)
        assert resp.status_code == 201


class TestCollectionResponse:
    def test_empty_collection(self):
        resp = collection_response([], "widget")
        body = json.loads(resp.body)
        assert body["data"] == []
        assert body["meta"]["total"] == 0
        assert body["meta"]["limit"] == 50
        assert body["meta"]["offset"] == 0

    def test_with_items(self):
        items = [{"id": "1", "name": "a"}, {"id": "2", "name": "b"}]
        resp = collection_response(items, "widget", total=10, limit=2, offset=0)
        body = json.loads(resp.body)
        assert len(body["data"]) == 2
        assert body["data"][0]["id"] == "1"
        assert body["data"][0]["type"] == "widget"
        assert body["data"][0]["attributes"]["name"] == "a"
        assert body["meta"]["total"] == 10

    def test_pagination_meta(self):
        resp = collection_response([], "x", total=100, limit=25, offset=50)
        body = json.loads(resp.body)
        assert body["meta"] == {"total": 100, "limit": 25, "offset": 50}


class TestErrorResponses:
    def test_error_response(self):
        resp = error_response("BAD", "something wrong", 400)
        body = json.loads(resp.body)
        assert resp.status_code == 400
        assert body["error"]["code"] == "BAD"
        assert body["error"]["message"] == "something wrong"

    def test_error_with_details(self):
        details = [{"field": "name", "message": "required"}]
        resp = error_response("VAL", "invalid", 422, details=details)
        body = json.loads(resp.body)
        assert body["error"]["details"] == details

    def test_not_found(self):
        resp = not_found("Widget", "abc")
        body = json.loads(resp.body)
        assert resp.status_code == 404
        assert body["error"]["code"] == "NOT_FOUND"
        assert "abc" in body["error"]["message"]

    def test_validation_error(self):
        resp = validation_error("bad input")
        assert resp.status_code == 422

    def test_conflict(self):
        resp = conflict("duplicate")
        assert resp.status_code == 409

    def test_server_error(self):
        resp = server_error()
        body = json.loads(resp.body)
        assert resp.status_code == 500
        assert body["error"]["code"] == "SERVER_ERROR"
