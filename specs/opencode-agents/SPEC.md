# OpenCode Agents Specification

## Goal

Multiple distinct OpenCode agent instances, each with a well-defined purpose, dedicated tools, and skills. Agents communicate via Redis pub/sub to form a signal processing pipeline.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MULTI-AGENT ARCHITECTURE                         │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  SIGNAL GENERATOR AGENT                                      │   │
│  │  Purpose: Analyze symbols, generate BUY/SELL/HOLD signals    │   │
│  │  Tools: strategy-mcp, market-data-mcp                        │   │
│  │  Skills: analyze-symbol, detect-patterns                     │   │
│  │  Frequency: Every 1 minute, parallel across symbols          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  OPPORTUNITY SCORER AGENT                                    │   │
│  │  Purpose: Rank signals by perceived upside                   │   │
│  │  Tools: backtest-mcp, market-data-mcp                        │   │
│  │  Skills: score-opportunity, calculate-expected-return        │   │
│  │  Trigger: On each new signal from Signal Generator           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  PORTFOLIO ADVISOR AGENT                                     │   │
│  │  Purpose: Consider portfolio state, risk limits              │   │
│  │  Tools: portfolio-mcp, backtest-mcp                          │   │
│  │  Skills: check-exposure, validate-position-size              │   │
│  │  Trigger: On high-opportunity signals (score > 70)           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  REPORT GENERATOR AGENT                                      │   │
│  │  Purpose: Create human-readable summaries for dashboard      │   │
│  │  Tools: decisions-mcp                                        │   │
│  │  Skills: generate-reasoning, create-summary                  │   │
│  │  Trigger: After signal pipeline completes                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  LEARNING AGENT                                              │   │
│  │  Purpose: Generate new strategy specs from top performers    │   │
│  │  Tools: strategy-db-mcp                                      │   │
│  │  Skills: few-shot-spec-generation, analyze-patterns          │   │
│  │  Trigger: Every 6 hours                                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  JANITOR AGENT                                               │   │
│  │  Purpose: Retire underperforming strategies                  │   │
│  │  Tools: strategy-db-mcp                                      │   │
│  │  Skills: evaluate-performance, recommend-retirement          │   │
│  │  Trigger: Daily (overnight)                                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Agent Configurations

### Directory Structure

```
agents/
├── signal-generator/
│   ├── .opencode/
│   │   └── config.json
│   ├── skills/
│   │   ├── analyze-symbol/
│   │   │   └── SKILL.md
│   │   └── detect-patterns/
│   │       └── SKILL.md
│   └── prompts/
│       └── system.md
│
├── opportunity-scorer/
│   ├── .opencode/
│   │   └── config.json
│   ├── skills/
│   │   ├── score-opportunity/
│   │   │   └── SKILL.md
│   │   └── calculate-expected-return/
│   │       └── SKILL.md
│   └── prompts/
│       └── system.md
│
├── portfolio-advisor/
│   ├── .opencode/
│   │   └── config.json
│   ├── skills/
│   │   ├── check-exposure/
│   │   │   └── SKILL.md
│   │   └── validate-position-size/
│   │       └── SKILL.md
│   └── prompts/
│       └── system.md
│
├── report-generator/
│   ├── .opencode/
│   │   └── config.json
│   ├── skills/
│   │   ├── generate-reasoning/
│   │   │   └── SKILL.md
│   │   └── create-summary/
│   │       └── SKILL.md
│   └── prompts/
│       └── system.md
│
├── learning/
│   ├── .opencode/
│   │   └── config.json
│   ├── skills/
│   │   ├── few-shot-spec-generation/
│   │   │   └── SKILL.md
│   │   └── analyze-patterns/
│   │       └── SKILL.md
│   └── prompts/
│       └── system.md
│
└── janitor/
    ├── .opencode/
    │   └── config.json
    ├── skills/
    │   ├── evaluate-performance/
    │   │   └── SKILL.md
    │   └── recommend-retirement/
    │       └── SKILL.md
    └── prompts/
        └── system.md
```

---

## Signal Generator Agent

### Configuration

```json
{
  "name": "signal-generator",
  "description": "Analyzes trading symbols and generates BUY/SELL/HOLD signals",
  "model": "google/gemini-3.0-flash",
  "mcp_servers": {
    "strategy-mcp": {
      "command": "python",
      "args": ["-m", "mcp_servers.strategy_mcp"],
      "env": {
        "DATABASE_URL": "${POSTGRES_URL}"
      }
    },
    "market-data-mcp": {
      "command": "python",
      "args": ["-m", "mcp_servers.market_data_mcp"],
      "env": {
        "INFLUXDB_URL": "${INFLUXDB_URL}"
      }
    }
  },
  "skills_dir": "./skills",
  "output": {
    "redis_channel": "channel:raw-signals"
  },
  "limits": {
    "timeout_seconds": 10,
    "max_tokens": 2000
  }
}
```

### System Prompt

```markdown
You are a trading signal analyst for TradeStream. Your job is to analyze trading symbols
using available tools and generate BUY/SELL/HOLD signals.

## Available Tools

- strategy-mcp: Get top strategies and their signals
- market-data-mcp: Get price and volatility data

## Workflow

1. Fetch top 5 strategies for the symbol
2. Get current signal from each strategy
3. Gather market context (price, volatility)
4. Synthesize findings into a trading signal

## Output Format

Return a JSON signal with:

- symbol, action, confidence
- strategy breakdown with individual signals
- reasoning explaining your decision
```

---

## Opportunity Scorer Agent

### Configuration

```json
{
  "name": "opportunity-scorer",
  "description": "Scores signals by opportunity potential",
  "model": "google/gemini-3.0-pro",
  "mcp_servers": {
    "backtest-mcp": {
      "command": "python",
      "args": ["-m", "mcp_servers.backtest_mcp"],
      "env": {
        "GRPC_HOST": "${BACKTEST_GRPC_HOST}"
      }
    },
    "market-data-mcp": {
      "command": "python",
      "args": ["-m", "mcp_servers.market_data_mcp"],
      "env": {
        "INFLUXDB_URL": "${INFLUXDB_URL}"
      }
    }
  },
  "skills_dir": "./skills",
  "input": {
    "redis_channel": "channel:raw-signals"
  },
  "output": {
    "redis_channel": "channel:scored-signals"
  },
  "limits": {
    "timeout_seconds": 5
  }
}
```

### System Prompt

```markdown
You are an opportunity scoring agent. You receive raw trading signals and enrich them
with opportunity scores based on multiple factors.

## Scoring Formula

opportunity_score = (
0.25 _ confidence +
0.30 _ normalize(expected_return) +
0.20 _ consensus_pct +
0.15 _ normalize(volatility) +
0.10 _ freshness
) _ 100

## Workflow

1. Receive raw signal from Signal Generator
2. Get historical performance for triggering strategies
3. Get current volatility
4. Calculate opportunity score
5. Publish enriched signal
```

---

## Portfolio Advisor Agent

### Configuration

```json
{
  "name": "portfolio-advisor",
  "description": "Validates signals against portfolio constraints",
  "model": "anthropic/claude-sonnet-4.5",
  "mcp_servers": {
    "portfolio-mcp": {
      "command": "python",
      "args": ["-m", "mcp_servers.portfolio_mcp"],
      "env": {
        "DATABASE_URL": "${POSTGRES_URL}"
      }
    },
    "backtest-mcp": {
      "command": "python",
      "args": ["-m", "mcp_servers.backtest_mcp"]
    }
  },
  "skills_dir": "./skills",
  "input": {
    "redis_channel": "channel:scored-signals",
    "min_opportunity_score": 70
  },
  "output": {
    "redis_channel": "channel:validated-signals"
  },
  "limits": {
    "timeout_seconds": 5
  }
}
```

### System Prompt

```markdown
You are a portfolio advisor agent. You receive high-opportunity signals and validate
them against portfolio constraints and risk limits.

## Validation Checks

1. Current exposure to this symbol
2. Total portfolio risk
3. Position size limits
4. Correlation with existing positions

## Output

Add validation status to signal:

- valid: boolean
- max_position_size: number
- risk_warnings: string[]
```

---

## Report Generator Agent

### Configuration

```json
{
  "name": "report-generator",
  "description": "Creates human-readable summaries for the dashboard",
  "model": "google/gemini-3.0-flash",
  "mcp_servers": {
    "decisions-mcp": {
      "command": "python",
      "args": ["-m", "mcp_servers.decisions_mcp"],
      "env": {
        "DATABASE_URL": "${POSTGRES_URL}"
      }
    }
  },
  "skills_dir": "./skills",
  "input": {
    "redis_channel": "channel:validated-signals"
  },
  "output": {
    "redis_channel": "channel:dashboard-signals",
    "sse_publish": true
  },
  "limits": {
    "timeout_seconds": 3
  }
}
```

### System Prompt

```markdown
You are a report generator agent. You create human-readable summaries of trading
signals for the dashboard.

## Output Format

- Clear, concise reasoning (2-3 sentences)
- Highlight key factors driving the decision
- Include any warnings or caveats
- Format for display in UI cards
```

---

## Learning Agent

### Configuration

```json
{
  "name": "learning",
  "description": "Generates new strategy specs from top performers",
  "model": "anthropic/claude-sonnet-4.5",
  "mcp_servers": {
    "strategy-db-mcp": {
      "command": "python",
      "args": ["-m", "mcp_servers.strategy_db_mcp"],
      "env": {
        "DATABASE_URL": "${POSTGRES_URL}"
      }
    }
  },
  "skills_dir": "./skills",
  "schedule": "0 */6 * * *",
  "limits": {
    "timeout_seconds": 300,
    "max_specs_per_run": 5
  }
}
```

### System Prompt

```markdown
You are a learning agent for TradeStream. You analyze top-performing strategies and
generate new strategy specs that build on successful patterns.

## Workflow

1. Fetch top 10 performing specs
2. Analyze common patterns
3. Generate 1-5 new specs that combine successful elements
4. Submit specs for GA optimization

## Constraints

- New specs must be unique (not duplicates)
- Must follow valid spec schema
- Include reasoning for why spec should work
```

---

## Janitor Agent

### Configuration

```json
{
  "name": "janitor",
  "description": "Retires underperforming strategies",
  "model": "google/gemini-3.0-flash",
  "mcp_servers": {
    "strategy-db-mcp": {
      "command": "python",
      "args": ["-m", "mcp_servers.strategy_db_mcp"],
      "env": {
        "DATABASE_URL": "${POSTGRES_URL}"
      }
    }
  },
  "skills_dir": "./skills",
  "schedule": "0 3 * * *",
  "limits": {
    "timeout_seconds": 600
  }
}
```

### System Prompt

```markdown
You are a janitor agent for TradeStream. You evaluate strategies for retirement based
on sustained poor performance.

## Retirement Criteria

All must be true:

- forward_trades >= 100
- age_days >= 180
- forward_sharpe < 0.5
- forward_accuracy < 0.45
- sharpe_trend == "DECLINING"
- better alternatives exist

## Constraints

- NEVER retire CANONICAL specs (original 70)
- Log reasoning for each retirement
- Generate summary report
```

---

## Inter-Agent Communication

### Redis Channels

```
channel:raw-signals        # Signal Generator → Opportunity Scorer
channel:scored-signals     # Opportunity Scorer → Portfolio Advisor
channel:validated-signals  # Portfolio Advisor → Report Generator
channel:dashboard-signals  # Report Generator → SSE Gateway
```

### Message Flow

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Signal     │───▶│ Opportunity  │───▶│  Portfolio   │───▶│   Report     │
│  Generator   │    │   Scorer     │    │   Advisor    │    │  Generator   │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
   raw-signals       scored-signals     validated-signals   dashboard-signals
                                                                   │
                                                                   ▼
                                                              SSE Stream
```

### Message Format

```json
{
  "message_id": "msg-abc123",
  "source_agent": "signal-generator",
  "timestamp": "2025-02-01T12:34:56Z",
  "payload": {
    "signal_id": "sig-xyz789",
    "symbol": "ETH/USD",
    "action": "BUY",
    "confidence": 0.82
  },
  "metadata": {
    "processing_time_ms": 450,
    "model_used": "google/gemini-3.0-flash"
  }
}
```

### Backpressure Mechanism

Each agent maintains a bounded input queue to prevent memory exhaustion during traffic spikes.

```python
@dataclass
class QueueConfig:
    max_size: int = 1000           # Maximum messages in queue
    high_watermark: float = 0.8    # 80% triggers slowdown signal
    low_watermark: float = 0.5     # 50% resumes normal processing
    drop_policy: str = "oldest"    # oldest | newest | reject

class BoundedMessageQueue:
    def __init__(self, config: QueueConfig):
        self.queue = asyncio.Queue(maxsize=config.max_size)
        self.config = config
        self.backpressure_active = False

    async def put(self, message: Message) -> bool:
        """Add message to queue with backpressure handling."""
        current_fill = self.queue.qsize() / self.config.max_size

        if current_fill >= self.config.high_watermark:
            self.backpressure_active = True
            await self.publish_backpressure_signal(active=True)

        if self.queue.full():
            if self.config.drop_policy == "oldest":
                try:
                    self.queue.get_nowait()
                    metrics.increment("messages_dropped", tags={"policy": "oldest"})
                except asyncio.QueueEmpty:
                    pass
            elif self.config.drop_policy == "newest":
                metrics.increment("messages_dropped", tags={"policy": "newest"})
                return False
            elif self.config.drop_policy == "reject":
                raise QueueFullError("Queue at capacity")

        await self.queue.put(message)
        return True

    async def get(self) -> Message:
        """Get message from queue and manage backpressure."""
        message = await self.queue.get()
        current_fill = self.queue.qsize() / self.config.max_size

        if self.backpressure_active and current_fill <= self.config.low_watermark:
            self.backpressure_active = False
            await self.publish_backpressure_signal(active=False)

        return message
```

### Retry Policy

Failed message processing uses exponential backoff with jitter to prevent thundering herd.

```python
@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay_ms: int = 100
    max_delay_ms: int = 10000
    exponential_base: float = 2.0
    jitter_factor: float = 0.1    # +/- 10% randomization

class RetryPolicy:
    def __init__(self, config: RetryConfig):
        self.config = config

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = min(
            self.config.base_delay_ms * (self.config.exponential_base ** attempt),
            self.config.max_delay_ms
        )
        jitter = delay * self.config.jitter_factor * (2 * random.random() - 1)
        return max(0, delay + jitter) / 1000

    async def execute_with_retry(self, func: Callable, message: Message) -> Result | None:
        """Execute function with retry logic."""
        last_error = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return await func(message)
            except RetryableError as e:
                last_error = e
                if attempt < self.config.max_retries:
                    delay = self.calculate_delay(attempt)
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}")
                    await asyncio.sleep(delay)
                    metrics.increment("retry_attempts", tags={"attempt": attempt + 1, "error_type": type(e).__name__})
            except NonRetryableError as e:
                logger.error(f"Non-retryable error: {e}")
                await self.send_to_dlq(message, e)
                return None

        logger.error(f"All {self.config.max_retries} retries exhausted: {last_error}")
        await self.send_to_dlq(message, last_error)
        return None

    async def send_to_dlq(self, message: Message, error: Exception):
        """Send failed message to dead letter queue."""
        dlq_message = {
            "original_message": message.to_dict(),
            "error": str(error),
            "error_type": type(error).__name__,
            "failed_at": datetime.utcnow().isoformat(),
            "retry_count": self.config.max_retries
        }
        await redis.lpush("dlq:agent-messages", json.dumps(dlq_message))
        metrics.increment("dlq_messages")
```

### Idempotency Enforcement

Each agent maintains a deduplication cache using `message_id` to ensure exactly-once processing.

```python
class IdempotencyEnforcer:
    def __init__(self, redis_client: Redis, ttl_seconds: int = 3600):
        self.redis = redis_client
        self.ttl = ttl_seconds
        self.key_prefix = "idempotency"

    async def is_duplicate(self, message: Message) -> bool:
        """Check if message was already processed."""
        key = f"{self.key_prefix}:{message.source_agent}:{message.message_id}"
        return await self.redis.exists(key)

    async def mark_processed(self, message: Message, result: Result):
        """Mark message as processed with result cached."""
        key = f"{self.key_prefix}:{message.source_agent}:{message.message_id}"
        value = {
            "processed_at": datetime.utcnow().isoformat(),
            "result_hash": hashlib.sha256(json.dumps(result.to_dict(), sort_keys=True).encode()).hexdigest()
        }
        await self.redis.setex(key, self.ttl, json.dumps(value))

class Agent:
    async def process_message(self, message: Message) -> Result | None:
        """Process message with idempotency check."""
        if await self.idempotency.is_duplicate(message):
            logger.info(f"Skipping duplicate message: {message.message_id}")
            metrics.increment("duplicate_messages_skipped")
            return await self.idempotency.get_cached_result(message)

        result = await self.retry_policy.execute_with_retry(self._do_process, message)

        if result:
            await self.idempotency.mark_processed(message, result)

        return result
```

---

## Learning/Janitor Agent Coordination

The Learning and Janitor agents both access `strategy-db-mcp` and could conflict when modifying strategy state.

### Mutual Exclusion via Distributed Lock

```python
class StrategyDbLock:
    """Distributed lock for strategy-db-mcp access."""

    LOCK_KEY = "lock:strategy-db-mcp"

    def __init__(self, redis_client: Redis, agent_name: str):
        self.redis = redis_client
        self.agent_name = agent_name
        self.lock_ttl = 600  # 10 minute max hold time

    async def acquire(self, timeout_seconds: int = 30) -> bool:
        """Attempt to acquire exclusive lock."""
        lock_value = f"{self.agent_name}:{uuid.uuid4()}"
        start = time.time()

        while time.time() - start < timeout_seconds:
            acquired = await self.redis.set(self.LOCK_KEY, lock_value, nx=True, ex=self.lock_ttl)
            if acquired:
                self._lock_value = lock_value
                logger.info(f"{self.agent_name} acquired strategy-db lock")
                return True
            await asyncio.sleep(1)

        return False

    async def release(self):
        """Release lock only if we hold it."""
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        await self.redis.eval(script, 1, self.LOCK_KEY, self._lock_value)

    async def __aenter__(self):
        if not await self.acquire():
            raise LockAcquisitionError(f"{self.agent_name} failed to acquire lock")
        return self

    async def __aexit__(self, *args):
        await self.release()
```

### Schedule Separation

| Agent    | Schedule      | Typical Duration | Notes                                      |
| -------- | ------------- | ---------------- | ------------------------------------------ |
| Learning | `0 */6 * * *` | 5-10 minutes     | Every 6 hours (00:00, 06:00, 12:00, 18:00) |
| Janitor  | `0 3 * * *`   | 10-30 minutes    | Daily at 03:00 UTC (off-peak)              |

### Operation Isolation

| Agent    | Read Operations          | Write Operations                  |
| -------- | ------------------------ | --------------------------------- |
| Learning | Top performers, patterns | `INSERT` new specs (DRAFT status) |
| Janitor  | Underperformers, metrics | `UPDATE` status to RETIRED        |

---

## Error Handling

### Agent Failure

```python
async def process_with_timeout(agent: Agent, message: Message) -> Result:
    try:
        result = await asyncio.wait_for(
            agent.process(message),
            timeout=agent.config.timeout_seconds
        )
        return result
    except asyncio.TimeoutError:
        logger.warning(f"Agent {agent.name} timed out for {message.payload.symbol}")
        # Continue pipeline with partial data
        return PartialResult(
            source=message,
            error="timeout",
            skip_to="report-generator"  # Skip to end of pipeline
        )
    except Exception as e:
        logger.error(f"Agent {agent.name} failed: {e}")
        # Publish error event to dashboard
        publish_error_event(agent.name, message, e)
        return None
```

### Pipeline Recovery

- Failed agents don't block the pipeline
- Partial signals continue with warnings
- Errors published to SSE for dashboard visibility
- Dead letter queue for failed messages

## Constraints

- Each agent runs as a separate process/container
- Agents must be idempotent (same input = same output)
- Agents must handle upstream failures gracefully
- Agents communicate via Redis pub/sub only (no direct calls)
- Total pipeline latency < 5 seconds (excluding backtest)

## Acceptance Criteria

- [ ] 6 distinct OpenCode agent configurations created
- [ ] Each agent has its own MCP servers and skills
- [ ] Inter-agent communication via Redis pub/sub works
- [ ] Signal pipeline processes 20 symbols in < 50 seconds
- [ ] Failed agent doesn't block the pipeline (timeout + skip)
- [ ] Error events published to SSE stream
- [ ] Learning agent generates valid specs
- [ ] Janitor agent respects CANONICAL protection
- [ ] Retry policy with exponential backoff implemented for all agents
- [ ] Backpressure mechanism prevents memory exhaustion under load
- [ ] Idempotency enforced via message_id deduplication
- [ ] Learning/Janitor agents coordinate via distributed lock
- [ ] Resource limits enforced per agent in Kubernetes deployment

## Deployment

### Docker Compose (Development)

```yaml
services:
  signal-generator:
    build:
      context: .
      dockerfile: agents/signal-generator/Dockerfile
    environment:
      - REDIS_URL=redis://redis:6379
      - POSTGRES_URL=postgresql://...
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}

  opportunity-scorer:
    build:
      context: .
      dockerfile: agents/opportunity-scorer/Dockerfile
    depends_on:
      - signal-generator
    environment:
      - REDIS_URL=redis://redis:6379

  # ... other agents
```

### Kubernetes (Production)

Each agent is a separate Deployment with:

- Resource limits (CPU, memory)
- HPA for scaling
- ConfigMap for agent config
- Secret for API keys

### Resource Limits per Agent

| Agent              | CPU Request | CPU Limit | Memory Request | Memory Limit | Max Queue Size |
| ------------------ | ----------- | --------- | -------------- | ------------ | -------------- |
| signal-generator   | 100m        | 500m      | 128Mi          | 512Mi        | 1000           |
| opportunity-scorer | 100m        | 500m      | 128Mi          | 512Mi        | 500            |
| portfolio-advisor  | 200m        | 1000m     | 256Mi          | 1Gi          | 200            |
| report-generator   | 50m         | 250m      | 64Mi           | 256Mi        | 500            |
| learning           | 500m        | 2000m     | 512Mi          | 2Gi          | N/A (batch)    |
| janitor            | 200m        | 1000m     | 256Mi          | 1Gi          | N/A (batch)    |

## Metrics

- `agent_pipeline_duration_ms` - End-to-end pipeline latency
- `agent_processing_duration_ms` - Per-agent processing time
- `agent_failures_total` - Failed agent invocations
- `agent_messages_processed_total` - Messages by agent and channel
- `agent_model_tokens_total` - Token usage by agent and model
- `agent_retry_attempts_total` - Retry attempts by agent and error type
- `agent_dlq_messages_total` - Messages sent to dead letter queue
- `agent_queue_size` - Current queue size per agent
- `agent_backpressure_active` - Backpressure state (0/1) per agent
- `agent_messages_dropped_total` - Messages dropped due to queue overflow
- `agent_duplicate_messages_skipped_total` - Duplicate messages filtered by idempotency
- `agent_lock_acquisition_duration_ms` - Time to acquire distributed lock
- `agent_lock_wait_total` - Lock acquisition attempts (success/failure)
