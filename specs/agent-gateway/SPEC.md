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
  | { type: 'session_start'; data: SessionStartEvent }
  | { type: 'signal'; data: TradingSignal }
  | { type: 'reasoning'; data: ReasoningStep }
  | { type: 'tool_call'; data: ToolCallEvent }
  | { type: 'tool_result'; data: ToolResultEvent }
  | { type: 'error'; data: ErrorEvent }
  | { type: 'backpressure_warning'; data: BackpressureWarning }
  | { type: 'heartbeat'; data: { timestamp: string } };

interface SessionStartEvent {
  session_id: string;
  timestamp: string;
}

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

interface BackpressureWarning {
  queue_size: number;
  queue_max: number;
  message: string;
  timestamp: string;
}

// All events are wrapped in an envelope with ordering metadata
interface EventEnvelope<T> {
  id: string;           // "{session_id}:{sequence_number}" for Last-Event-ID
  sequence: number;     // Monotonically increasing per session
  event: T;
}
```

### SSE Stream Format

```
event: session_start
id: sess-123:1
data: {"session_id":"sess-123","timestamp":"2025-02-01T12:34:00Z"}

event: signal
id: sess-123:2
data: {"signal_id":"abc123","symbol":"ETH/USD","action":"BUY","confidence":0.82,...}

event: reasoning
id: sess-123:3
data: {"signal_id":"abc123","step":1,"content":"Analyzing top strategies..."}

event: tool_call
id: sess-123:4
data: {"signal_id":"abc123","tool_name":"get_top_strategies","parameters":{"symbol":"ETH/USD"}}

event: tool_result
id: sess-123:5
data: {"signal_id":"abc123","tool_name":"get_top_strategies","result":[...],"latency_ms":45}

event: heartbeat
id: sess-123:6
data: {"timestamp":"2025-02-01T12:34:56Z"}
```

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT GATEWAY                            │
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │ SSE Handler │◄───│ Event Queue │◄───│ Kafka Consumer  │ │
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
              Kafka Topics: agent-signals-raw
                           agent-signals-scored
                           agent-dashboard-signals
```

### Session Management

- Each SSE connection has a unique `session_id` returned in the initial `session_start` event
- The `session_id` must be included in subsequent `/api/agent/command` requests to correlate events
- Event queues are per-session with configurable max size (default: 1000 events)
- Idle sessions cleaned up after 5 minutes of no activity (cleanup runs every 60 seconds)
- Reconnection support via `Last-Event-ID` header

#### Session Flow

```
1. Client connects to /api/agent/stream
2. Server generates session_id, returns session_start event:
   event: session_start
   id: sess-123:1
   data: {"session_id":"sess-123","timestamp":"..."}

3. Client stores session_id for subsequent commands
4. Client POSTs to /api/agent/command with session_id
5. Agent events stream back on the SSE connection filtered by session_id
```

#### Session Cleanup Timing

- Cleanup task runs every 60 seconds
- Sessions are marked inactive after 5 minutes of no client activity
- Inactive sessions are removed in batches (max 100 per cleanup cycle)
- On cleanup, pending events in the session queue are discarded
- Client reconnecting after cleanup receives a new session_id

### Connection Limits and Backpressure

#### Per-Client Limits
- Maximum 5 concurrent SSE connections per IP address
- Exceeding limit returns HTTP 429 Too Many Requests
- Connection tracking via in-memory LRU cache (10,000 entries max)

#### Backpressure Handling
- **Queue monitoring**: When queue reaches 80% capacity (800 events), emit `backpressure_warning` event
- **Slow consumer detection**: If queue stays above 80% for 30 seconds, disconnect client with `slow_consumer` error
- **Graceful degradation**: Under backpressure, reduce event granularity (skip intermediate reasoning steps, keep signals)
- **Queue overflow**: When queue is full, drop oldest events with FIFO eviction

### Rate Limiting

MVP includes basic rate limiting per IP:

| Endpoint | Limit |
|----------|-------|
| `/api/agent/stream` | 10 connections/minute per IP |
| `/api/agent/command` | 60 requests/minute per IP |
| `/api/agent/health` | 120 requests/minute per IP |

Rate limit responses include standard headers:
- `X-RateLimit-Limit`: Requests allowed per window
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when window resets

### Event Ordering Guarantees

- Events for a given `signal_id` are delivered in causal order
- Each event includes a monotonic `sequence_number` within its session
- Cross-signal event ordering is best-effort (no global ordering guarantee)
- `Last-Event-ID` format: `{session_id}:{sequence_number}`
- Reconnection resumes from the next sequence number

### Reconnection Strategy

Clients should implement exponential backoff with jitter:

| Attempt | Base Delay | Max Jitter | Max Delay |
|---------|------------|------------|-----------|
| 1 | 1s | 0.5s | 1.5s |
| 2 | 2s | 1s | 3s |
| 3 | 4s | 2s | 6s |
| 4 | 8s | 4s | 12s |
| 5+ | 16s | 8s | 24s |

- Maximum retry attempts: 10 (then surface error to user)
- Reset retry counter after 60 seconds of stable connection
- Include `Last-Event-ID` header to resume from last received event

### Command Endpoint

```http
POST /api/agent/command
Content-Type: application/json

{
  "session_id": "sess-123",
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

**Note**: The `session_id` field is required to correlate command responses with the correct SSE stream. If omitted, the server returns HTTP 400 with error `missing_session_id`.

## Constraints

- Must handle 100+ concurrent SSE connections
- Event delivery latency < 100ms from Kafka publish to client receive
- Heartbeat every 30 seconds to keep connections alive
- Graceful degradation if Kafka unavailable (return cached last signals)
- No authentication in MVP (add in Phase 2)

## Dependencies

- Kafka (existing cluster used by TradeStream services)
- Flask with SSE support (consistent with other TradeStream Python services)
- Existing `strategy_monitor_api` for health checks

## Configuration

```yaml
agent_gateway:
  host: 0.0.0.0
  port: 8081
  kafka:
    bootstrap_servers: kafka:9092
    group_id: agent-gateway-group
    topics:
      - agent-signals-raw
      - agent-signals-scored
      - agent-dashboard-signals
  sse:
    heartbeat_interval_seconds: 30
    max_queue_size: 1000
    session_timeout_seconds: 300
    session_cleanup_interval_seconds: 60
    backpressure_threshold_percent: 80
    slow_consumer_timeout_seconds: 30
  rate_limiting:
    stream_connections_per_minute: 10
    commands_per_minute: 60
    health_requests_per_minute: 120
  connection_limits:
    max_connections_per_ip: 5
    ip_tracking_cache_size: 10000
  cors:
    allowed_origins:
      - http://localhost:3000
      - https://dashboard.tradestream.io
```

## Acceptance Criteria

- [ ] SSE endpoint delivers events within 100ms of Kafka publish
- [ ] Supports 100+ concurrent connections without degradation
- [ ] Auto-reconnect works across network interruptions (via Last-Event-ID)
- [ ] Health endpoint reports connection count and Kafka status
- [ ] Command endpoint queues queries and returns request ID
- [ ] Heartbeat events sent every 30 seconds
- [ ] Session cleanup after 5 minutes of inactivity
- [ ] CORS configured for dashboard origins
- [ ] Rate limiting enforced per IP with standard headers
- [ ] Backpressure warning emitted at 80% queue capacity
- [ ] Slow consumers disconnected after 30 seconds of sustained backpressure
- [ ] Events include sequence numbers for ordering

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
│   ├── kafka_subscriber.py  # Kafka consumer
│   ├── session_manager.py   # SSE session management
│   ├── event_queue.py       # Per-session event queuing
│   ├── rate_limiter.py      # IP-based rate limiting
│   └── backpressure.py      # Backpressure detection and handling
├── models/
│   └── events.py        # Event type definitions
├── requirements.txt
├── Dockerfile
└── tests/
    ├── test_stream.py
    ├── test_commands.py
    ├── test_rate_limiting.py
    └── test_backpressure.py
```

## API Examples

### Connect to SSE Stream

```bash
curl -N -H "Accept: text/event-stream" \
  "http://localhost:8081/api/agent/stream"
```

### Reconnect with Last-Event-ID

```bash
curl -N -H "Accept: text/event-stream" \
  -H "Last-Event-ID: sess-123:42" \
  "http://localhost:8081/api/agent/stream"
```

### Submit Interactive Query

```bash
curl -X POST "http://localhost:8081/api/agent/command" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sess-123", "query": "Should I buy ETH?", "symbol": "ETH/USD"}'
```

### Health Check

```bash
curl "http://localhost:8081/api/agent/health"
# {"status":"healthy","connections":42,"kafka":"connected","uptime_seconds":3600}
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Kafka disconnected | Return cached signals, log warning, attempt reconnect |
| Queue overflow | Drop oldest events, log warning |
| Invalid command | Return 400 with validation errors |
| Agent timeout | Stream error event, return partial results if available |
| Missing session_id | Return 400 with `missing_session_id` error |
| Rate limit exceeded | Return 429 with rate limit headers |
| Connection limit exceeded | Return 429 with `connection_limit_exceeded` error |
| Slow consumer detected | Close SSE connection with `slow_consumer` error event |

## Metrics to Expose

- `agent_gateway_connections_active` - Current SSE connections
- `agent_gateway_connections_per_ip` - Connections grouped by IP
- `agent_gateway_events_published_total` - Events sent by type
- `agent_gateway_event_latency_ms` - Time from Kafka to client
- `agent_gateway_commands_total` - Commands received
- `agent_gateway_errors_total` - Errors by type
- `agent_gateway_rate_limit_hits_total` - Rate limit rejections by endpoint
- `agent_gateway_backpressure_warnings_total` - Backpressure warnings emitted
- `agent_gateway_slow_consumer_disconnects_total` - Slow consumer disconnections
- `agent_gateway_queue_size` - Current queue size per session (histogram)
