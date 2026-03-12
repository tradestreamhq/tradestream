"""Trade Journal HTTP service.

Provides REST endpoints for logging trade decisions, querying journal
entries, and exporting data in CSV/JSON formats.
"""

from flask import Flask, jsonify, request

from services.shared.auth import flask_auth_middleware
from services.trade_journal.exporter import to_csv, to_json
from services.trade_journal.journal import TradeJournal


def create_app(journal: TradeJournal) -> Flask:
    """Create the Flask application with trade journal endpoints."""
    app = Flask(__name__)
    flask_auth_middleware(app)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "healthy", "service": "trade-journal"})

    @app.route("/journal/entries", methods=["POST"])
    def create_entry():
        """Log a new trade journal entry.

        Request body:
            trade_id: Unique trade identifier
            strategy: Strategy name
            symbol: Trading symbol
            side: BUY or SELL
            entry_price: Entry price
            entry_rationale: Reasoning for the entry
            signals_at_entry: (optional) Signal snapshot at entry time
            tags: (optional) List of tags
        """
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        required = ["trade_id", "strategy", "symbol", "side", "entry_price", "entry_rationale"]
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

        try:
            entry = journal.log_entry(
                trade_id=data["trade_id"],
                strategy=data["strategy"],
                symbol=data["symbol"],
                side=data["side"],
                entry_price=float(data["entry_price"]),
                entry_rationale=data["entry_rationale"],
                signals_at_entry=data.get("signals_at_entry"),
                tags=data.get("tags"),
            )
            return jsonify(entry.to_dict()), 201
        except (ValueError, KeyError) as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/journal/entries/<entry_id>/close", methods=["POST"])
    def close_entry(entry_id):
        """Close a journal entry with exit analysis.

        Request body:
            exit_price: Exit price
            exit_rationale: Reasoning for the exit
            lessons: (optional) Lessons learned
        """
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        exit_price = data.get("exit_price")
        exit_rationale = data.get("exit_rationale")
        if exit_price is None or not exit_rationale:
            return jsonify({"error": "exit_price and exit_rationale are required"}), 400

        try:
            entry = journal.close_entry(
                entry_id=entry_id,
                exit_price=float(exit_price),
                exit_rationale=exit_rationale,
                lessons=data.get("lessons"),
            )
            return jsonify(entry.to_dict())
        except KeyError as e:
            return jsonify({"error": str(e)}), 404

    @app.route("/journal/entries/<entry_id>", methods=["GET"])
    def get_entry(entry_id):
        entry = journal.get_entry(entry_id)
        if entry is None:
            return jsonify({"error": "Entry not found"}), 404
        return jsonify(entry.to_dict())

    @app.route("/journal/entries", methods=["GET"])
    def list_entries():
        """List/search journal entries.

        Query params:
            strategy: Filter by strategy
            symbol: Filter by symbol
            outcome: Filter by outcome (WIN/LOSS/BREAKEVEN/OPEN)
            side: Filter by side (BUY/SELL)
            start_date: Filter by start date (ISO format)
            end_date: Filter by end date (ISO format)
            tags: Comma-separated tag filter
        """
        tags_param = request.args.get("tags")
        tags = tags_param.split(",") if tags_param else None

        entries = journal.search(
            strategy=request.args.get("strategy"),
            symbol=request.args.get("symbol"),
            outcome=request.args.get("outcome"),
            side=request.args.get("side"),
            start_date=request.args.get("start_date"),
            end_date=request.args.get("end_date"),
            tags=tags,
        )
        return jsonify({
            "entries": [e.to_dict() for e in entries],
            "count": len(entries),
        })

    @app.route("/journal/summary", methods=["GET"])
    def summary():
        """Get summary statistics.

        Query params:
            strategy: Filter by strategy
            symbol: Filter by symbol
        """
        stats = journal.summary(
            strategy=request.args.get("strategy"),
            symbol=request.args.get("symbol"),
        )
        return jsonify(stats)

    @app.route("/journal/export/csv", methods=["GET"])
    def export_csv():
        """Export entries as CSV. Supports same filters as list endpoint."""
        tags_param = request.args.get("tags")
        tags = tags_param.split(",") if tags_param else None

        entries = journal.search(
            strategy=request.args.get("strategy"),
            symbol=request.args.get("symbol"),
            outcome=request.args.get("outcome"),
            side=request.args.get("side"),
            start_date=request.args.get("start_date"),
            end_date=request.args.get("end_date"),
            tags=tags,
        )
        csv_data = to_csv(entries)
        return app.response_class(csv_data, mimetype="text/csv")

    @app.route("/journal/export/json", methods=["GET"])
    def export_json():
        """Export entries as JSON. Supports same filters as list endpoint."""
        tags_param = request.args.get("tags")
        tags = tags_param.split(",") if tags_param else None

        entries = journal.search(
            strategy=request.args.get("strategy"),
            symbol=request.args.get("symbol"),
            outcome=request.args.get("outcome"),
            side=request.args.get("side"),
            start_date=request.args.get("start_date"),
            end_date=request.args.get("end_date"),
            tags=tags,
        )
        json_data = to_json(entries)
        return app.response_class(json_data, mimetype="application/json")

    return app
