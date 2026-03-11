"""Tests for the shared API key authentication middleware."""

import os
from unittest.mock import patch

import pytest
from flask import Flask, jsonify

from services.shared.auth import flask_auth_middleware


def _create_test_app():
    """Create a minimal Flask app with auth middleware for testing."""
    app = Flask(__name__)
    flask_auth_middleware(app)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok"})

    @app.route("/data")
    def data():
        return jsonify({"value": 42})

    return app


class TestFlaskAuthMiddleware:
    """Tests for Flask API key auth middleware."""

    def test_health_endpoint_bypasses_auth(self):
        app = _create_test_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            with app.test_client() as client:
                resp = client.get("/health")
                assert resp.status_code == 200

    def test_api_health_endpoint_bypasses_auth(self):
        app = _create_test_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            with app.test_client() as client:
                resp = client.get("/api/health")
                assert resp.status_code == 200

    def test_no_key_configured_allows_all(self):
        app = _create_test_app()
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("TRADESTREAM_API_KEY", None)
            with app.test_client() as client:
                resp = client.get("/data")
                assert resp.status_code == 200

    def test_valid_api_key(self):
        app = _create_test_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            with app.test_client() as client:
                resp = client.get("/data", headers={"X-API-Key": "secret123"})
                assert resp.status_code == 200

    def test_invalid_api_key(self):
        app = _create_test_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            with app.test_client() as client:
                resp = client.get("/data", headers={"X-API-Key": "wrong"})
                assert resp.status_code == 401

    def test_missing_api_key_header(self):
        app = _create_test_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            with app.test_client() as client:
                resp = client.get("/data")
                assert resp.status_code == 401

    def test_401_response_body(self):
        app = _create_test_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            with app.test_client() as client:
                resp = client.get("/data")
                data = resp.get_json()
                assert data["error"] == "Invalid or missing API key"
