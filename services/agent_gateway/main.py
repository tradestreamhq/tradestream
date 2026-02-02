"""
Agent Gateway Service

SSE-based backend service that streams agent events to connected frontends.

Endpoints:
- GET /api/agent/stream - SSE stream of agent events
- POST /api/agent/command - Accept user queries
- GET /api/health - Health check
"""

import json
import logging
import os
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from queue import Queue, Empty
from threading import Lock
from typing import Any, Dict, Generator, List, Optional

from flask import Flask, Response, request, jsonify
from flask_cors import CORS

from kafka_pubsub import KafkaPubSub, AgentMessage, Topics


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Flask app
app = Flask(__name__)
CORS(app)


@dataclass
class SSEEvent:
    """Server-Sent Event."""

    event: str
    data: Dict[str, Any]
    id: Optional[str] = None
    retry: Optional[int] = None

    def serialize(self) -> str:
        """Serialize to SSE format."""
        lines = []
        if self.id:
            lines.append(f"id: {self.id}")
        if self.retry:
            lines.append(f"retry: {self.retry}")
        lines.append(f"event: {self.event}")
        lines.append(f"data: {json.dumps(self.data)}")
        lines.append("")  # Empty line to end the event
        return "\n".join(lines) + "\n"


@dataclass
class ClientSession:
    """Represents a connected SSE client."""

    session_id: str
    queue: Queue = field(default_factory=lambda: Queue(maxsize=100))
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_event_id: int = 0
    filters: Dict[str, Any] = field(default_factory=dict)

    def send_event(self, event: SSEEvent) -> bool:
        """Add event to client's queue. Returns False if queue is full."""
        try:
            self.queue.put_nowait(event)
            return True
        except:
            return False


class SessionManager:
    """Manages SSE client sessions."""

    def __init__(self, max_sessions: int = 1000, session_ttl: int = 3600):
        self.sessions: Dict[str, ClientSession] = {}
        self.max_sessions = max_sessions
        self.session_ttl = session_ttl
        self._lock = Lock()
        self._sequence_counter = 0

    def create_session(self) -> ClientSession:
        """Create a new client session."""
        with self._lock:
            # Cleanup old sessions if at capacity
            if len(self.sessions) >= self.max_sessions:
                self._cleanup_old_sessions()

            session_id = str(uuid.uuid4())
            session = ClientSession(session_id=session_id)
            self.sessions[session_id] = session
            logger.info(f"Created session: {session_id}")
            return session

    def get_session(self, session_id: str) -> Optional[ClientSession]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        """Remove a session."""
        with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"Removed session: {session_id}")

    def broadcast(self, event: SSEEvent) -> int:
        """Broadcast event to all connected clients. Returns count of recipients."""
        with self._lock:
            self._sequence_counter += 1
            event.id = f"evt-{self._sequence_counter}"

        count = 0
        for session in list(self.sessions.values()):
            if session.send_event(event):
                count += 1
        return count

    def _cleanup_old_sessions(self) -> None:
        """Remove expired sessions."""
        now = datetime.utcnow()
        expired = []
        for sid, session in self.sessions.items():
            age = (now - session.created_at).total_seconds()
            if age > self.session_ttl:
                expired.append(sid)

        for sid in expired[:100]:  # Limit cleanup batch
            del self.sessions[sid]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")


# Global instances
session_manager = SessionManager()
kafka_pubsub: Optional[KafkaPubSub] = None


def init_kafka():
    """Initialize Kafka connection."""
    global kafka_pubsub

    kafka_pubsub = KafkaPubSub()

    # Subscribe to dashboard signals topic
    def on_dashboard_signal(message: AgentMessage):
        """Handle incoming dashboard signals from agents."""
        event = SSEEvent(
            event=message.message_type,
            data=message.to_dict(),
        )
        count = session_manager.broadcast(event)
        logger.debug(f"Broadcast {message.message_type} to {count} clients")

    kafka_pubsub.subscribe(Topics.DASHBOARD_SIGNALS, on_dashboard_signal)
    kafka_pubsub.start_listening()
    logger.info("Kafka Pub/Sub initialized and listening")


# Routes


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    kafka_ok = kafka_pubsub.ping() if kafka_pubsub else False
    return jsonify({
        "status": "healthy" if kafka_ok else "degraded",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "kafka": "connected" if kafka_ok else "disconnected",
        "active_sessions": len(session_manager.sessions),
    })


@app.route("/api/health/live", methods=["GET"])
def health_live():
    """Kubernetes liveness probe."""
    return jsonify({"status": "ok"})


@app.route("/api/health/ready", methods=["GET"])
def health_ready():
    """Kubernetes readiness probe."""
    kafka_ok = kafka_pubsub.ping() if kafka_pubsub else False
    if not kafka_ok:
        return jsonify({"status": "not ready", "reason": "kafka disconnected"}), 503
    return jsonify({"status": "ready"})


@app.route("/api/agent/stream", methods=["GET"])
def agent_stream():
    """SSE endpoint for streaming agent events."""

    def generate() -> Generator[str, None, None]:
        # Create session
        session = session_manager.create_session()

        # Send session_start event
        start_event = SSEEvent(
            event="session_start",
            data={"session_id": session.session_id},
            retry=3000,  # 3 second reconnect
        )
        yield start_event.serialize()

        try:
            while True:
                try:
                    # Get event from queue with timeout
                    event = session.queue.get(timeout=30)
                    yield event.serialize()
                except Empty:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            session_manager.remove_session(session.session_id)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@app.route("/api/agent/command", methods=["POST"])
def agent_command():
    """Accept user commands/queries for the agent."""
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    query = data.get("query")
    if not query:
        return jsonify({"error": "query required"}), 400

    # Verify session exists
    session = session_manager.get_session(session_id)
    if not session:
        return jsonify({"error": "Invalid session_id"}), 404

    # Create command message
    command_id = str(uuid.uuid4())
    command_message = AgentMessage(
        message_id=command_id,
        message_type="user_command",
        source_agent="gateway",
        timestamp=datetime.utcnow().isoformat() + "Z",
        payload={
            "query": query,
            "session_id": session_id,
            "symbol": data.get("symbol"),
        },
        correlation_id=command_id,
    )

    # Publish to agent command topic
    if kafka_pubsub:
        kafka_pubsub.publish(Topics.AGENT_COMMANDS, command_message)

    # Send acknowledgment event to the client
    ack_event = SSEEvent(
        event="command_received",
        data={
            "command_id": command_id,
            "query": query,
            "status": "processing",
        },
    )
    session.send_event(ack_event)

    return jsonify({
        "command_id": command_id,
        "status": "accepted",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


@app.route("/api/agent/sessions", methods=["GET"])
def list_sessions():
    """List active sessions (admin endpoint)."""
    sessions = []
    for sid, session in session_manager.sessions.items():
        sessions.append({
            "session_id": sid,
            "created_at": session.created_at.isoformat() + "Z",
            "queue_size": session.queue.qsize(),
        })
    return jsonify({
        "sessions": sessions,
        "count": len(sessions),
    })


def main():
    """Run the agent gateway service."""
    # Get configuration
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8081"))

    # Initialize Kafka
    init_kafka()

    logger.info(f"Starting Agent Gateway on {host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
