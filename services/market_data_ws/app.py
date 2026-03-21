"""Market Data WebSocket Gateway.

Provides real-time market data streaming via WebSocket connections.
Clients subscribe to channels like "trades:BTC-USD", "candles:ETH-USD:1m",
or "orderbook:BTC-USD" to receive live updates.
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from services.market_data_ws.broadcaster import MarketDataBroadcaster
from services.rest_api_shared.health import create_health_router

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONNECTIONS_PER_CLIENT = 5
HEARTBEAT_INTERVAL_SECONDS = 30
HEARTBEAT_TIMEOUT_SECONDS = 10


def create_app(
    broadcaster: MarketDataBroadcaster | None = None,
    max_connections_per_client: int = DEFAULT_MAX_CONNECTIONS_PER_CLIENT,
) -> FastAPI:
    """Create the Market Data WebSocket Gateway application."""
    app = FastAPI(
        title="Market Data WebSocket Gateway",
        version="1.0.0",
        docs_url="/docs",
    )

    if broadcaster is None:
        broadcaster = MarketDataBroadcaster()
    app.state.broadcaster = broadcaster

    # Track connections per client identifier (IP-based for simplicity)
    client_connections: Dict[str, int] = defaultdict(int)

    app.include_router(create_health_router("market-data-ws"))

    @app.websocket("/ws/market-data")
    async def market_data_ws(ws: WebSocket):
        client_id = ws.client.host if ws.client else "unknown"

        if client_connections[client_id] >= max_connections_per_client:
            await ws.accept()
            await ws.send_json(
                {
                    "type": "error",
                    "error": "max_connections_exceeded",
                    "message": f"Maximum {max_connections_per_client} connections per client",
                }
            )
            await ws.close(code=1008)
            return

        await ws.accept()
        client_connections[client_id] += 1
        heartbeat_task = None

        try:
            await ws.send_json(
                {
                    "type": "connected",
                    "heartbeat_interval": HEARTBEAT_INTERVAL_SECONDS,
                    "max_connections": max_connections_per_client,
                }
            )

            heartbeat_task = asyncio.create_task(
                _heartbeat_loop(ws, HEARTBEAT_INTERVAL_SECONDS)
            )

            while True:
                data = await ws.receive_json()
                await _handle_message(ws, data, broadcaster)

        except WebSocketDisconnect:
            logger.info("Client %s disconnected", client_id)
        except Exception:
            logger.exception("WebSocket error for client %s", client_id)
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()
            await broadcaster.disconnect(ws)
            client_connections[client_id] = max(0, client_connections[client_id] - 1)
            if client_connections[client_id] == 0:
                del client_connections[client_id]

    return app


async def _handle_message(
    ws: WebSocket, data: dict, broadcaster: MarketDataBroadcaster
):
    """Route an incoming client message to the appropriate handler."""
    msg_type = data.get("type")

    if msg_type == "subscribe":
        channel = data.get("channel", "")
        if not MarketDataBroadcaster.validate_channel(channel):
            await ws.send_json(
                {
                    "type": "error",
                    "error": "invalid_channel",
                    "message": f"Invalid channel: {channel}",
                }
            )
            return
        added = await broadcaster.subscribe(ws, channel)
        await ws.send_json(
            {
                "type": "subscribed",
                "channel": channel,
                "already_subscribed": not added,
            }
        )

    elif msg_type == "unsubscribe":
        channel = data.get("channel", "")
        removed = await broadcaster.unsubscribe(ws, channel)
        await ws.send_json(
            {
                "type": "unsubscribed",
                "channel": channel,
                "was_subscribed": removed,
            }
        )

    elif msg_type == "ping":
        await ws.send_json({"type": "pong", "timestamp": time.time()})

    elif msg_type == "list_subscriptions":
        channels = await broadcaster.get_client_channels(ws)
        await ws.send_json({"type": "subscriptions", "channels": sorted(channels)})

    else:
        await ws.send_json(
            {
                "type": "error",
                "error": "unknown_message_type",
                "message": f"Unknown message type: {msg_type}",
            }
        )


async def _heartbeat_loop(ws: WebSocket, interval: int):
    """Send periodic heartbeat pings to keep the connection alive."""
    try:
        while True:
            await asyncio.sleep(interval)
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.send_json({"type": "heartbeat", "timestamp": time.time()})
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
