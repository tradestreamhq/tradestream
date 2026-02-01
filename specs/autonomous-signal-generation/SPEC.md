# Autonomous Signal Generation Specification

## Goal

Background service that runs the OpenCode agent pipeline every 1 minute to generate trading signals autonomously, without user interaction.

## Target Behavior

The autonomous runner is a scheduled service that:
1. Triggers Signal Generator for all active symbols every 1 minute
2. Processes symbols in parallel using OpenCode's Task tool
3. Coordinates the full agent pipeline (Signal → Score → Advise → Report)
4. Handles overruns and failures gracefully
5. Publishes signals to SSE stream even with no users connected

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 AUTONOMOUS SIGNAL RUNNER                    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Scheduler (CronJob)                                  │   │
│  │ Schedule: */1 * * * * (every minute)                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│                              ▼                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Coordinator Process                                  │   │
│  │                                                      │   │
│  │  1. Check for previous run locks                    │   │
│  │  2. Get active symbols from config                  │   │
│  │  3. Spawn parallel subagents per symbol             │   │
│  │  4. Aggregate results                               │   │
│  │  5. Publish to Redis                                │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│         ┌───────────────────┼───────────────────┐          │
│         ▼                   ▼                   ▼          │
│  ┌────────────┐      ┌────────────┐      ┌────────────┐   │
│  │ Subagent   │      │ Subagent   │      │ Subagent   │   │
│  │ ETH/USD    │      │ BTC/USD    │      │ SOL/USD    │   │
│  └────────────┘      └────────────┘      └────────────┘   │
│         │                   │                   │          │
│         └───────────────────┼───────────────────┘          │
│                              ▼                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Redis: channel:raw-signals                          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Processing Timeline

```
Minute 0:00 - Scheduler triggers
Minute 0:01 - Coordinator acquires lock, fetches symbol list
Minute 0:02 - Spawns 20 parallel subagents
Minute 0:03-0:45 - Subagents analyze symbols (10s each, parallel)
Minute 0:46 - Results aggregated, published to Redis
Minute 0:47-0:50 - Pipeline continues (Scorer → Advisor → Report)
Minute 0:51 - Signals appear on dashboard
Minute 1:00 - Next cycle begins
```

## Multi-Agent Coordination

### OpenCode Task Tool Usage

```python
# Coordinator prompt
"""
Analyze all active symbols for trading signals. Process them in parallel.

Active symbols: {symbols}

For each symbol, use the Task tool to spawn a subagent that:
1. Calls analyze-symbol skill
2. Returns structured signal

Aggregate all results and publish to Redis.
"""

# OpenCode internally spawns subagents
task_calls = [
    Task(
        prompt=f"Analyze {symbol} and generate trading signal",
        agent_type="signal-generator",
        parallel=True
    )
    for symbol in symbols
]
```

### Subagent Invocation

Each subagent runs the Signal Generator configuration:
- Inherits MCP servers from parent config
- Has 10-second timeout per symbol
- Returns structured signal JSON
- Failures don't block other symbols

## Overrun Protection

### Redis Lock Per Symbol

```python
LOCK_KEY = "signal:lock:{symbol}"
LOCK_TTL = 90  # seconds

async def acquire_lock(symbol: str) -> bool:
    """Try to acquire processing lock for symbol."""
    return await redis.set(
        LOCK_KEY.format(symbol=symbol),
        value=str(time.time()),
        nx=True,  # Only set if not exists
        ex=LOCK_TTL
    )

async def release_lock(symbol: str):
    """Release processing lock."""
    await redis.delete(LOCK_KEY.format(symbol=symbol))
```

### Overrun Handling

```python
async def process_symbol(symbol: str) -> Optional[Signal]:
    if not await acquire_lock(symbol):
        logger.warning(f"Symbol {symbol} still processing from previous run, skipping")
        metrics.increment("signal_generation_skipped", tags={"symbol": symbol})
        return None

    try:
        signal = await run_signal_generator(symbol)
        return signal
    finally:
        await release_lock(symbol)
```

### Overrun Scenarios

| Scenario | Behavior |
|----------|----------|
| Previous run still active | Skip locked symbols, log warning |
| Single slow symbol | Continue with others, timeout slow one |
| All symbols slow | Partial results published, metrics alert |
| Redis unavailable | Skip locking, proceed with caution |

## Rate Limit Management

### OpenRouter Limits

```python
# Default OpenRouter rate: ~100 requests/minute
# 20 symbols × 4 tool calls each = 80 requests/minute (within limit)

RATE_LIMIT_CONFIG = {
    "requests_per_minute": 100,
    "symbols_per_minute": 20,
    "max_concurrent_symbols": 10,  # Process in batches if needed
    "retry_delay_seconds": 5,
    "max_retries": 2
}
```

### Batch Processing (if needed)

```python
async def process_symbols_batched(symbols: list[str]) -> list[Signal]:
    """Process symbols in batches to respect rate limits."""
    batch_size = RATE_LIMIT_CONFIG["max_concurrent_symbols"]
    results = []

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        batch_results = await asyncio.gather(
            *[process_symbol(s) for s in batch],
            return_exceptions=True
        )
        results.extend([r for r in batch_results if r and not isinstance(r, Exception)])

        # Brief pause between batches if needed
        if i + batch_size < len(symbols):
            await asyncio.sleep(1)

    return results
```

## Configuration

### Scheduler Config

```yaml
autonomous_runner:
  schedule: "*/1 * * * *"  # Every minute
  timezone: "UTC"
  symbols:
    - ETH/USD
    - BTC/USD
    - SOL/USD
    - DOGE/USD
    - AVAX/USD
    - MATIC/USD
    - LINK/USD
    - UNI/USD
    - AAVE/USD
    - SNX/USD
    - CRV/USD
    - COMP/USD
    - MKR/USD
    - SUSHI/USD
    - YFI/USD
    - 1INCH/USD
    - BAL/USD
    - LDO/USD
    - RPL/USD
    - FXS/USD
  parallel:
    max_concurrent: 10
    batch_delay_ms: 1000
  timeouts:
    symbol_timeout_seconds: 10
    total_timeout_seconds: 50
  locks:
    ttl_seconds: 90
    redis_key_prefix: "signal:lock:"
  retry:
    max_attempts: 2
    delay_seconds: 5
```

### Environment Variables

```bash
# Required
OPENROUTER_API_KEY=sk-or-...
REDIS_URL=redis://localhost:6379
POSTGRES_URL=postgresql://...
INFLUXDB_URL=http://influxdb:8086

# Optional
SIGNAL_FREQUENCY_MINUTES=1
MAX_SYMBOLS=20
LOG_LEVEL=INFO
```

## Implementation

### Main Runner

```python
# services/autonomous_runner/main.py

import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Config
from .coordinator import SignalCoordinator
from .metrics import metrics

logger = logging.getLogger(__name__)

class AutonomousRunner:
    def __init__(self, config: Config):
        self.config = config
        self.coordinator = SignalCoordinator(config)
        self.scheduler = AsyncIOScheduler()

    async def start(self):
        """Start the autonomous signal generation scheduler."""
        self.scheduler.add_job(
            self.run_cycle,
            CronTrigger.from_crontab(self.config.schedule),
            id="signal_generation",
            replace_existing=True
        )
        self.scheduler.start()
        logger.info(f"Autonomous runner started with schedule: {self.config.schedule}")

    async def run_cycle(self):
        """Execute one signal generation cycle."""
        cycle_start = datetime.utcnow()
        logger.info(f"Starting signal generation cycle at {cycle_start}")

        try:
            signals = await self.coordinator.process_all_symbols(
                self.config.symbols
            )
            metrics.gauge("signals_generated", len(signals))
            logger.info(f"Generated {len(signals)} signals in cycle")

        except Exception as e:
            logger.error(f"Signal generation cycle failed: {e}")
            metrics.increment("cycle_failures")

        finally:
            duration = (datetime.utcnow() - cycle_start).total_seconds()
            metrics.timing("cycle_duration_seconds", duration)
            logger.info(f"Cycle completed in {duration:.2f}s")

    async def stop(self):
        """Stop the scheduler gracefully."""
        self.scheduler.shutdown(wait=True)
        logger.info("Autonomous runner stopped")
```

### Coordinator

```python
# services/autonomous_runner/coordinator.py

import asyncio
from typing import List, Optional

from .lock_manager import LockManager
from .opencode_client import OpenCodeClient
from .redis_publisher import RedisPublisher

class SignalCoordinator:
    def __init__(self, config):
        self.config = config
        self.lock_manager = LockManager(config.redis_url)
        self.opencode = OpenCodeClient(config)
        self.publisher = RedisPublisher(config.redis_url)

    async def process_all_symbols(self, symbols: List[str]) -> List[Signal]:
        """Process all symbols in parallel batches."""
        results = []
        batch_size = self.config.parallel.max_concurrent

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            batch_results = await self._process_batch(batch)
            results.extend(batch_results)

            if i + batch_size < len(symbols):
                await asyncio.sleep(self.config.parallel.batch_delay_ms / 1000)

        # Publish all signals
        for signal in results:
            await self.publisher.publish("channel:raw-signals", signal)

        return results

    async def _process_batch(self, symbols: List[str]) -> List[Signal]:
        """Process a batch of symbols in parallel."""
        tasks = [self._process_symbol(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        signals = []
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to process {symbol}: {result}")
            elif result:
                signals.append(result)

        return signals

    async def _process_symbol(self, symbol: str) -> Optional[Signal]:
        """Process a single symbol with lock protection."""
        if not await self.lock_manager.acquire(symbol):
            logger.warning(f"Symbol {symbol} locked, skipping")
            return None

        try:
            signal = await asyncio.wait_for(
                self.opencode.analyze_symbol(symbol),
                timeout=self.config.timeouts.symbol_timeout_seconds
            )
            return signal
        except asyncio.TimeoutError:
            logger.warning(f"Timeout processing {symbol}")
            return None
        finally:
            await self.lock_manager.release(symbol)
```

## Metrics and Monitoring

### Prometheus Metrics

```python
# Counters
signal_generation_total{symbol, action}
signal_generation_skipped{symbol, reason}
cycle_failures_total

# Gauges
signals_generated_last_cycle
active_locks
symbols_processing

# Histograms
cycle_duration_seconds
symbol_processing_duration_seconds{symbol}
```

### Health Endpoint

```python
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "last_cycle": last_cycle_time.isoformat(),
        "signals_last_cycle": signals_count,
        "active_locks": await lock_manager.count_active(),
        "redis_connected": await redis.ping()
    }
```

### Alerts

```yaml
# prometheus-alerts.yaml
groups:
  - name: autonomous-runner
    rules:
      - alert: SignalGenerationDelayed
        expr: time() - autonomous_runner_last_cycle_timestamp > 120
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Signal generation hasn't run in 2+ minutes"

      - alert: HighSkipRate
        expr: rate(signal_generation_skipped_total[5m]) > 0.3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "More than 30% of symbols being skipped"
```

## Deployment

### Kubernetes CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: signal-generator
spec:
  schedule: "*/1 * * * *"
  concurrencyPolicy: Forbid  # Don't run if previous still running
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      activeDeadlineSeconds: 55  # Kill if takes too long
      template:
        spec:
          restartPolicy: Never
          containers:
            - name: runner
              image: tradestream/autonomous-runner:latest
              env:
                - name: OPENROUTER_API_KEY
                  valueFrom:
                    secretKeyRef:
                      name: openrouter-secrets
                      key: api-key
                - name: REDIS_URL
                  value: redis://redis:6379
              resources:
                requests:
                  memory: "512Mi"
                  cpu: "250m"
                limits:
                  memory: "1Gi"
                  cpu: "500m"
```

### Alternative: Long-Running Service

For lower latency, run as a long-running service with internal scheduler:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: autonomous-runner
spec:
  replicas: 1  # Single instance to avoid duplicate runs
  selector:
    matchLabels:
      app: autonomous-runner
  template:
    spec:
      containers:
        - name: runner
          image: tradestream/autonomous-runner:latest
          command: ["python", "-m", "autonomous_runner.main", "--mode=service"]
```

## Constraints

- Must complete 20 symbols in < 50 seconds (10s buffer before next cycle)
- Must not exceed OpenRouter rate limits (~100 req/min)
- Graceful degradation if LLM unavailable (skip cycle, alert)
- Signals timestamped for deduplication
- Dashboard shows signals even with no users connected
- Single instance running (no duplicate cycles)

## Acceptance Criteria

- [ ] Signals generated for 20 symbols every 1 minute
- [ ] Parallel processing via batched subagent invocation
- [ ] Overrun protection with Redis locks
- [ ] Failed symbols logged but don't block others
- [ ] Dashboard shows signals even with no users connected
- [ ] Metrics: processing time per symbol, success rate
- [ ] Health endpoint reports status
- [ ] Alerts fire on failures or delays

## File Structure

```
services/autonomous_runner/
├── __init__.py
├── main.py                  # Entry point
├── config.py                # Configuration loading
├── coordinator.py           # Signal coordination logic
├── lock_manager.py          # Redis lock management
├── opencode_client.py       # OpenCode invocation
├── redis_publisher.py       # Redis pub/sub
├── metrics.py               # Prometheus metrics
├── requirements.txt
├── Dockerfile
└── tests/
    ├── test_coordinator.py
    └── test_lock_manager.py
```
