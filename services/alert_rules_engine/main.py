"""Entry point for the Alert Rules Engine service.

Provides:
  - A REST API for CRUD operations on alert rules
  - A background evaluation loop that checks rules periodically
  - Redis Pub/Sub listener for real-time signal and regime events
"""

import json
import signal
import sys
import threading

import redis
from absl import app, flags, logging
from flask import Flask, jsonify, request

from services.alert_rules_engine.config import get_config
from services.alert_rules_engine.engine import AlertEngine
from services.alert_rules_engine.models import (
    ActionType,
    AlertAction,
    AlertCondition,
    AlertRule,
    ConditionType,
)
from services.alert_rules_engine.rule_store import RuleStore
from services.shared.structured_logger import StructuredLogger

FLAGS = flags.FLAGS

flags.DEFINE_string("redis_host", None, "Redis host (overrides REDIS_HOST env var).")
flags.DEFINE_integer("redis_port", None, "Redis port (overrides REDIS_PORT env var).")

_shutdown = False
_log = StructuredLogger(service_name="alert_rules_engine")


def _handle_shutdown(signum, frame):
    global _shutdown
    _log.info("Received shutdown signal", signum=signum)
    _shutdown = True


def create_api(rule_store: RuleStore, engine: AlertEngine) -> Flask:
    """Create the Flask REST API for alert rule management."""
    flask_app = Flask(__name__)

    @flask_app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "alert_rules_engine"})

    @flask_app.route("/rules", methods=["GET"])
    def list_rules():
        rules = rule_store.list_all()
        return jsonify({"rules": [r.to_dict() for r in rules]})

    @flask_app.route("/rules", methods=["POST"])
    def create_rule():
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        try:
            condition = AlertCondition(
                condition_type=ConditionType(data["condition"]["condition_type"]),
                params=data["condition"].get("params", {}),
            )
            action = AlertAction(
                action_type=ActionType(data["action"]["action_type"]),
                params=data["action"].get("params", {}),
            )
            rule = AlertRule(
                rule_id="",
                name=data.get("name", "Unnamed Rule"),
                condition=condition,
                action=action,
                cooldown_seconds=data.get("cooldown_seconds", 300),
                enabled=data.get("enabled", True),
            )
            rule_store.create(rule)
            return jsonify(rule.to_dict()), 201
        except (KeyError, ValueError) as e:
            return jsonify({"error": str(e)}), 400

    @flask_app.route("/rules/<rule_id>", methods=["GET"])
    def get_rule(rule_id):
        rule = rule_store.get(rule_id)
        if rule is None:
            return jsonify({"error": "Rule not found"}), 404
        return jsonify(rule.to_dict())

    @flask_app.route("/rules/<rule_id>", methods=["PUT"])
    def update_rule(rule_id):
        existing = rule_store.get(rule_id)
        if existing is None:
            return jsonify({"error": "Rule not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        try:
            if "condition" in data:
                existing.condition = AlertCondition(
                    condition_type=ConditionType(data["condition"]["condition_type"]),
                    params=data["condition"].get("params", {}),
                )
            if "action" in data:
                existing.action = AlertAction(
                    action_type=ActionType(data["action"]["action_type"]),
                    params=data["action"].get("params", {}),
                )
            if "name" in data:
                existing.name = data["name"]
            if "cooldown_seconds" in data:
                existing.cooldown_seconds = data["cooldown_seconds"]
            if "enabled" in data:
                existing.enabled = data["enabled"]

            rule_store.update(existing)
            return jsonify(existing.to_dict())
        except (KeyError, ValueError) as e:
            return jsonify({"error": str(e)}), 400

    @flask_app.route("/rules/<rule_id>", methods=["DELETE"])
    def delete_rule(rule_id):
        if rule_store.delete(rule_id):
            return jsonify({"deleted": True})
        return jsonify({"error": "Rule not found"}), 404

    @flask_app.route("/rules/<rule_id>/enable", methods=["POST"])
    def enable_rule(rule_id):
        rule = rule_store.get(rule_id)
        if rule is None:
            return jsonify({"error": "Rule not found"}), 404
        rule.enabled = True
        rule_store.update(rule)
        return jsonify(rule.to_dict())

    @flask_app.route("/rules/<rule_id>/disable", methods=["POST"])
    def disable_rule(rule_id):
        rule = rule_store.get(rule_id)
        if rule is None:
            return jsonify({"error": "Rule not found"}), 404
        rule.enabled = False
        rule_store.update(rule)
        return jsonify(rule.to_dict())

    @flask_app.route("/events", methods=["GET"])
    def list_events():
        count = request.args.get("count", 50, type=int)
        events = rule_store.get_recent_events(count)
        return jsonify({"events": events})

    @flask_app.route("/evaluate", methods=["POST"])
    def trigger_evaluation():
        """Manually trigger an evaluation cycle."""
        events = engine.evaluate_all()
        return jsonify(
            {
                "evaluated": True,
                "alerts_fired": len(events),
                "events": [
                    {"rule_name": e.rule_name, "message": e.message} for e in events
                ],
            }
        )

    return flask_app


def _listen_signals(redis_client, engine: AlertEngine):
    """Subscribe to Redis signal and regime channels to feed the engine."""
    pubsub = redis_client.pubsub()
    pubsub.psubscribe("signals:*")
    pubsub.subscribe("regime:changes")

    _log.info("Signal/regime listener started")

    while not _shutdown:
        message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if message is None:
            continue

        data = message.get("data")
        if not data or not isinstance(data, str):
            continue

        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            continue

        channel = message.get("channel", "")
        if isinstance(channel, bytes):
            channel = channel.decode()

        if channel == "regime:changes":
            engine.set_regime(parsed)
        else:
            engine.set_signal(parsed)

    pubsub.close()


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    _log.new_correlation_id()

    config = get_config()

    redis_host = FLAGS.redis_host or config["redis_host"]
    redis_port = FLAGS.redis_port or config["redis_port"]

    _log.info("Connecting to Redis", host=redis_host, port=redis_port)
    client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    client.ping()
    _log.info("Connected to Redis")

    rule_store = RuleStore(client)
    engine = AlertEngine(
        rule_store=rule_store,
        portfolio_url=config["portfolio_url"],
        market_data_url=config["market_data_url"],
    )

    # Background thread: evaluation loop
    eval_thread = threading.Thread(
        target=engine.run_loop,
        kwargs={
            "interval_seconds": config["eval_interval_seconds"],
            "shutdown_flag": lambda: _shutdown,
        },
        daemon=True,
        name="alert-eval-loop",
    )
    eval_thread.start()

    # Background thread: signal/regime listener
    listener_thread = threading.Thread(
        target=_listen_signals,
        args=(client, engine),
        daemon=True,
        name="alert-signal-listener",
    )
    listener_thread.start()

    # Foreground: REST API
    flask_app = create_api(rule_store, engine)
    api_port = config["api_port"]
    _log.info("Alert Rules Engine starting", port=api_port)
    flask_app.run(host="0.0.0.0", port=api_port)


if __name__ == "__main__":
    app.run(main)
