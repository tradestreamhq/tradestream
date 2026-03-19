"""Dashboard API — exposes orchestration funnel metrics and status."""

import json

from flask import Flask, jsonify
from flask_cors import CORS

from services.agent_orchestration import config


def create_dashboard_app(state):
    """Create a Flask app exposing orchestration dashboard endpoints.

    Args:
        state: OrchestrationState instance (shared with orchestration loop).

    Returns:
        Flask app.
    """
    app = Flask(__name__)
    CORS(app)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "healthy", "cycle": state.cycle_number})

    @app.route("/api/orchestration/status", methods=["GET"])
    def orchestration_status():
        """Overall orchestration status."""
        promoted = state.get_promoted_strategies()
        return jsonify({
            "cycle_number": state.cycle_number,
            "last_cycle_time": state.last_cycle_time,
            "total_candidates": len(state.candidates),
            "promoted_count": len(promoted),
            "total_promotions": len(state.promotion_history),
            "total_retirements": len(state.retirement_history),
        })

    @app.route("/api/orchestration/funnel", methods=["GET"])
    def discovery_funnel():
        """Discovery funnel: generated -> validated -> promoted -> live."""
        candidates = state.candidates.values()
        by_phase = {}
        for c in candidates:
            by_phase.setdefault(c.phase, []).append(c.to_dict())

        return jsonify({
            "discovery": len(by_phase.get(config.PHASE_DISCOVERY, [])),
            "validation": len(by_phase.get(config.PHASE_VALIDATION, [])),
            "promoted": len(by_phase.get(config.PHASE_PROMOTION, [])),
            "phases": {
                phase: [
                    {"name": c["name"], "allocation": c.get("allocation_weight", 0)}
                    for c in recs
                ]
                for phase, recs in by_phase.items()
            },
        })

    @app.route("/api/orchestration/promoted", methods=["GET"])
    def promoted_strategies():
        """List all currently promoted (live) strategies with metrics."""
        promoted = state.get_promoted_strategies()
        return jsonify({
            "strategies": [
                {
                    "name": c.name,
                    "allocation_weight": c.allocation_weight,
                    "metrics": c.metrics,
                    "promoted_since": c.created_at,
                }
                for c in promoted
            ]
        })

    @app.route("/api/orchestration/history", methods=["GET"])
    def cycle_history():
        """Recent cycle stats."""
        recent = state.cycle_stats[-50:]
        return jsonify({"cycles": recent})

    @app.route("/api/orchestration/promotions", methods=["GET"])
    def promotion_history():
        """Full promotion history."""
        return jsonify({"promotions": state.promotion_history[-100:]})

    @app.route("/api/orchestration/retirements", methods=["GET"])
    def retirement_history():
        """Full retirement history."""
        return jsonify({"retirements": state.retirement_history[-100:]})

    return app
