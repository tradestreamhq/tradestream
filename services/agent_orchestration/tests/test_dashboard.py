"""Tests for the dashboard API."""

import json
import os
import tempfile

from services.agent_orchestration import config
from services.agent_orchestration.dashboard import create_dashboard_app
from services.agent_orchestration.state import OrchestrationState


class TestDashboardAPI:
    def _setup(self):
        tmp = tempfile.mkdtemp()
        state = OrchestrationState(state_file=os.path.join(tmp, "state.json"))
        state.cycle_number = 3
        state.add_candidate("disc_1", {})
        state.add_candidate("val_1", {})
        state.advance_to_validation("val_1", {"sharpe_ratio": 1.0})
        state.add_candidate("live_1", {})
        state.promote("live_1", 0.1)
        state.record_cycle_stats({"discovered": 5, "promoted": 1})

        app = create_dashboard_app(state)
        app.config["TESTING"] = True
        return app.test_client(), state

    def test_health(self):
        client, _ = self._setup()
        resp = client.get("/health")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "healthy"
        assert data["cycle"] == 3

    def test_status(self):
        client, _ = self._setup()
        resp = client.get("/api/orchestration/status")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["cycle_number"] == 3
        assert data["total_candidates"] == 3
        assert data["promoted_count"] == 1
        assert data["total_promotions"] == 1

    def test_funnel(self):
        client, _ = self._setup()
        resp = client.get("/api/orchestration/funnel")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["discovery"] == 1
        assert data["validation"] == 1
        assert data["promoted"] == 1

    def test_promoted(self):
        client, _ = self._setup()
        resp = client.get("/api/orchestration/promoted")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["strategies"]) == 1
        assert data["strategies"][0]["name"] == "live_1"
        assert data["strategies"][0]["allocation_weight"] == 0.1

    def test_history(self):
        client, _ = self._setup()
        resp = client.get("/api/orchestration/history")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["cycles"]) == 1

    def test_promotions(self):
        client, _ = self._setup()
        resp = client.get("/api/orchestration/promotions")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["promotions"]) == 1

    def test_retirements(self):
        client, _ = self._setup()
        resp = client.get("/api/orchestration/retirements")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["retirements"]) == 0
