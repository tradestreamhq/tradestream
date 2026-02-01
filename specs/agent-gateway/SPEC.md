# Agent Gateway Service Specification

## Goal

SSE-based backend service that streams agent events to connected frontends, enabling real-time visibility into agent reasoning, tool calls, and trading signals.

## Target Behavior

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/agent/stream` | GET (SSE) | Real-time event stream for connected clients |
| `/api/agent/command` | POST | Submit user queries to the agent |
| `/api/agent/health` | GET | Service health and connection metrics |

### Event Types

```typescript
type AgentEvent =
  | { type: 'signal'; data: TradingSignal }
  | { type: 'reasoning'; data: ReasoningStep }
  | { type: 'tool_call'; data: ToolCallEvent }
  | { type: 'tool_result'; data: ToolResultEvent }
  | { type: 'error'; data: ErrorEvent }
  | { type: 'heartbeat'; data: { timestamp: string } };

interface TradingSignal {
  signal_id: string;
  symbol: string;
  action: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  opportunity_score: number;
  summary: string;
  timestamp: string;
}

interface ReasoningStep {
  signal_id: string;
  step: number;
  content: string;
  timestamp: string;
}

interface ToolCallEvent {
  signal_id: string;
  tool_name: string;
  parameters: Record<string, unknown>;
  timestamp: string;
}

interface ToolResultEvent {
  signal_id: string;
  tool_name: string;
  result: unknown;
  latency_ms: number;
  timestamp: string;
}

interface ErrorEvent {
  signal_id?: string;
  error_code: string;
  message: string;
  timestamp: string;
}
```

### SSE Stream Format

```
event: signal
data: {"signal_id":"abc123","symbol":"ETH/USD","action":"BUY","confidence":0.82,...}

event: reasoning
data: {"signal_id":"abc123","step":1,"content":"Analyzing top strategies..."}

event: tool_call
data: {"signal_id":"abc123","tool_name":"get_top_strategies","parameters":{"symbol":"ETH/USD"}}

event: tool_result
data: {"signal_id":"abc123","tool_name":"get_top_strategies","result":[...],"latency_ms":45}

event: heartbeat
data: {"timestamp":"2025-02-01T12:34:56Z"}
```

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT GATEWAY                            │
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │ SSE Handler │◄───│ Event Queue │◄───│ Redis Pub/Sub   │ │
│  │ (per client)│    │ (per session)│    │ Subscriber      │ │
│  └─────────────┘    └─────────────┘    └─────────────────┘ │
│         │                                      ▲            │
│         ▼                                      │            │
│  ┌─────────────┐                     ┌─────────────────┐   │
│  │ HTTP Server │                     │ Agent Pipeline  │   │
│  │ (FastAPI)   │                     │ Events          │   │
│  └─────────────┘                     └─────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
              Redis Channels: channel:signals
                             channel:reasoning
                             channel:tool-events
```

### Session Management

- Each SSE connection has a unique `session_id`
- Event queues are per-session with configurable max size (default: 1000 events)
- Idle sessions cleaned up after 5 minutes of no activity
- Reconnection support via `Last-Event-ID` header

### Command Endpoint

```http
POST /api/agent/command
Content-Type: application/json

{
  "session_id": "optional-session-id",
  "query": "What about DOGE right now?",
  "symbol": "DOGE/USD"
}
```

Response:
```json
{
  "request_id": "req-456",
  "session_id": "sess-123",
  "status": "processing",
  "message": "Query submitted. Events will stream on /api/agent/stream"
}
```

## Constraints

- Must handle 100+ concurrent SSE connections
- Event delivery latency < 100ms from Redis publish to client receive
- Heartbeat every 30 seconds to keep connections alive
- Graceful degradation if Redis unavailable (return cached last signals)
- No authentication in MVP (add in Phase 2)

## Dependencies

- Redis 7.x for pub/sub
- FastAPI with `sse-starlette` for SSE support
- Existing `strategy_monitor_api` for health checks

## Configuration

```yaml
agent_gateway:
  host: 0.0.0.0
  port: 8081
  redis:
    url: redis://localhost:6379
    channels:
      - channel:signals
      - channel:reasoning
      - channel:tool-events
  sse:
    heartbeat_interval_seconds: 30
    max_queue_size: 1000
    session_timeout_seconds: 300
  cors:
    allowed_origins:
      - http://localhost:3000
      - https://dashboard.tradestream.io
```

## Acceptance Criteria

- [ ] SSE endpoint delivers events within 100ms of Redis publish
- [ ] Supports 100+ concurrent connections without degradation
- [ ] Auto-reconnect works across network interruptions (via Last-Event-ID)
- [ ] Health endpoint reports connection count and Redis status
- [ ] Command endpoint queues queries and returns request ID
- [ ] Heartbeat events sent every 30 seconds
- [ ] Session cleanup after 5 minutes of inactivity
- [ ] CORS configured for dashboard origins

## File Structure

```
services/agent_gateway/
├── main.py              # FastAPI application entry
├── config.py            # Configuration loading
├── routes/
│   ├── stream.py        # SSE streaming endpoint
│   ├── command.py       # Command submission endpoint
│   └── health.py        # Health check endpoint
├── services/
│   ├── redis_subscriber.py  # Redis pub/sub consumer
│   ├── session_manager.py   # SSE session management
│   └── event_queue.py       # Per-session event queuing
├── models/
│   └── events.py        # Event type definitions
├── requirements.txt
├── Dockerfile
└── tests/
    ├── test_stream.py
    └── test_commands.py
```

## API Examples

### Connect to SSE Stream

```bash
curl -N -H "Accept: text/event-stream" \
  "http://localhost:8081/api/agent/stream"
```

### Submit Interactive Query

```bash
curl -X POST "http://localhost:8081/api/agent/command" \
  -H "Content-Type: application/json" \
  -d '{"query": "Should I buy ETH?", "symbol": "ETH/USD"}'
```

### Health Check

```bash
curl "http://localhost:8081/api/agent/health"
# {"status":"healthy","connections":42,"redis":"connected","uptime_seconds":3600}
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Redis disconnected | Return cached signals, log warning, attempt reconnect |
| Queue overflow | Drop oldest events, log warning |
| Invalid command | Return 400 with validation errors |
| Agent timeout | Stream error event, return partial results if available |

## Metrics to Expose

- `agent_gateway_connections_active` - Current SSE connections
- `agent_gateway_events_published_total` - Events sent by type
- `agent_gateway_event_latency_ms` - Time from Redis to client
- `agent_gateway_commands_total` - Commands received
- `agent_gateway_errors_total` - Errors by type
