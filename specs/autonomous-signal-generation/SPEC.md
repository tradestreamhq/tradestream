# Autonomous Signal Generation Specification

## Goal

Background service that runs the OpenCode agent pipeline every 1 minute to generate trading signals autonomously, without user interaction.

## Target Behavior

The autonomous runner is a scheduled service that:

1. Triggers Signal Generator for all active symbols every 1 minute
2. Processes symbols in parallel using OpenCode's Task tool
3. Coordinates the full agent pipeline (Signal -> Score -> Advise -> Report)
4. Handles overruns and failures gracefully
5. Publishes signals to SSE stream even with no users connected

### Architecture

```
+-------------------------------------------------------------+
|                 AUTONOMOUS SIGNAL RUNNER                    |
|                                                             |
|  +-----------------------------------------------------+   |
|  | Scheduler (CronJob)                                  |   |
|  | Schedule: */1 * * * * (every minute)                 |   |
|  +-----------------------------------------------------+   |
|                              |                              |
|                              v                              |
|  +-----------------------------------------------------+   |
|  | Coordinator Process                                  |   |
|  |                                                      |   |
|  |  1. Check circuit breaker state                     |   |
|  |  2. Check for previous run locks                    |   |
|  |  3. Get active symbols from config                  |   |
|  |  4. Spawn parallel subagents per symbol             |   |
|  |  5. Aggregate results                               |   |
|  |  6. Publish to Redis                                |   |
|  +-----------------------------------------------------+   |
|                              |                              |
|         +-------------------+-------------------+          |
|         v                   v                   v          |
|  +------------+      +------------+      +------------+   |
|  | Subagent   |      | Subagent   |      | Subagent   |   |
|  | ETH/USD    |      | BTC/USD    |      | SOL/USD    |   |
|  +------------+      +------------+      +------------+   |
|         |                   |                   |          |
|         +-------------------+-------------------+          |
|                              v                              |
|  +-----------------------------------------------------+   |
|  | Redis: channel:raw-signals                          |   |
|  +-----------------------------------------------------+   |
+-------------------------------------------------------------+
```

### Processing Timeline

```
Minute 0:00 - Scheduler triggers
Minute 0:01 - Coordinator checks circuit breaker, acquires lock, fetches symbol list
Minute 0:02 - Spawns 20 parallel subagents
Minute 0:03-0:45 - Subagents analyze symbols (10s each, parallel)
Minute 0:46 - Results aggregated, published to Redis
Minute 0:47-0:50 - Pipeline continues (Scorer -> Advisor -> Report)
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

## Circuit Breaker Pattern

To prevent cascading failures when the LLM service or dependencies are degraded, implement a circuit breaker:

### Circuit Breaker States

```
+---------+   failure_threshold    +------+   recovery_timeout   +-----------+
| CLOSED  | ---------------------> | OPEN | ------------------> | HALF_OPEN |
+---------+                        +------+                      +-----------+
     ^                                  |                             |
     |                                  |                             |
     |         success                  | failure                     | success
     +----------------------------------+-----------------------------+
```

| State     | Behavior                                            |
| --------- | --------------------------------------------------- |
| CLOSED    | Normal operation, requests allowed                  |
| OPEN      | All requests rejected, waiting for recovery timeout |
| HALF_OPEN | Limited test requests allowed to check recovery     |

### Circuit Breaker Implementation

```python
# services/autonomous_runner/circuit_breaker.py

from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Rejecting requests
    HALF_OPEN = "half_open"  # Testing recovery

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5        # Failures before opening
    recovery_timeout: int = 60        # Seconds before trying half-open
    half_open_max_calls: int = 3      # Test calls in half-open state
    success_threshold: int = 2        # Successes to close from half-open

class CircuitBreaker:
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if not self.allow_request():
            metrics.increment("circuit_breaker_rejected", tags={"breaker": self.name})
            raise CircuitBreakerOpenError(f"Circuit {self.name} is open")

        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise

    def allow_request(self) -> bool:
        """Check if request should be allowed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if self._should_attempt_recovery():
                self._transition_to_half_open()
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            # Allow limited requests in half-open
            self.half_open_calls += 1
            return self.half_open_calls <= self.config.half_open_max_calls

        return False

    def on_success(self):
        """Record successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        else:
            self.failure_count = 0  # Reset failure count on success

    def on_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.state == CircuitState.HALF_OPEN:
            self._transition_to_open()
        elif self.failure_count >= self.config.failure_threshold:
            self._transition_to_open()

    def _should_attempt_recovery(self) -> bool:
        if self.last_failure_time is None:
            return True
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.config.recovery_timeout

    def _transition_to_open(self):
        logger.warning(f"Circuit {self.name} OPEN after {self.failure_count} failures")
        self.state = CircuitState.OPEN
        self.half_open_calls = 0
        self.success_count = 0
        metrics.gauge("circuit_breaker_state", 1, tags={"breaker": self.name, "state": "open"})

    def _transition_to_half_open(self):
        logger.info(f"Circuit {self.name} HALF_OPEN, testing recovery")
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.success_count = 0
        metrics.gauge("circuit_breaker_state", 0.5, tags={"breaker": self.name, "state": "half_open"})

    def _transition_to_closed(self):
        logger.info(f"Circuit {self.name} CLOSED, recovered")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        metrics.gauge("circuit_breaker_state", 0, tags={"breaker": self.name, "state": "closed"})
```

### Circuit Breaker Configuration

```yaml
autonomous_runner:
  circuit_breaker:
    llm_service:
      failure_threshold: 5
      recovery_timeout_seconds: 60
      half_open_max_calls: 3
      success_threshold: 2
    redis:
      failure_threshold: 3
      recovery_timeout_seconds: 30
      half_open_max_calls: 2
      success_threshold: 1
```

## Overrun Protection

### Redis Lock Per Symbol

```python
LOCK_KEY = "signal:lock:{symbol}"
LOCK_TTL = 90  # seconds
LOCK_STALE_THRESHOLD = 120  # seconds - consider lock stale after this

async def acquire_lock(symbol: str, instance_id: str) -> bool:
    """Try to acquire processing lock for symbol."""
    lock_value = json.dumps({
        "instance_id": instance_id,
        "acquired_at": time.time(),
        "pid": os.getpid()
    })
    return await redis.set(
        LOCK_KEY.format(symbol=symbol),
        value=lock_value,
        nx=True,  # Only set if not exists
        ex=LOCK_TTL
    )

async def release_lock(symbol: str, instance_id: str):
    """Release processing lock only if we own it (using Lua for atomicity)."""
    lua_script = """
    local lock_data = redis.call('GET', KEYS[1])
    if lock_data then
        local data = cjson.decode(lock_data)
        if data.instance_id == ARGV[1] then
            return redis.call('DEL', KEYS[1])
        end
    end
    return 0
    """
    await redis.eval(lua_script, keys=[LOCK_KEY.format(symbol=symbol)], args=[instance_id])
```

### Stale Lock Recovery

When a process crashes while holding a lock, the lock may remain until TTL expires. This mechanism detects and recovers stale locks proactively:

```python
HEARTBEAT_KEY = "runner:heartbeat:{instance_id}"
HEARTBEAT_TTL = 30  # seconds
HEARTBEAT_INTERVAL = 10  # seconds

class StaleLockRecovery:
    def __init__(self, redis_client, instance_id: str):
        self.redis = redis_client
        self.instance_id = instance_id
        self._heartbeat_task = None

    async def start_heartbeat(self):
        """Start background heartbeat task."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop_heartbeat(self):
        """Stop heartbeat task gracefully."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _heartbeat_loop(self):
        """Maintain heartbeat to indicate this instance is alive."""
        while True:
            try:
                await self.redis.set(
                    HEARTBEAT_KEY.format(instance_id=self.instance_id),
                    json.dumps({"timestamp": time.time(), "pid": os.getpid()}),
                    ex=HEARTBEAT_TTL
                )
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            except asyncio.CancelledError:
                # Clean up heartbeat on shutdown
                await self.redis.delete(HEARTBEAT_KEY.format(instance_id=self.instance_id))
                raise
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")
                await asyncio.sleep(1)  # Brief retry delay

    async def check_and_recover_stale_lock(self, symbol: str) -> bool:
        """Check if lock is stale and recover it if so.

        A lock is considered stale if:
        1. It has existed longer than LOCK_STALE_THRESHOLD, OR
        2. The owning instance's heartbeat is missing

        Returns True if lock was recovered and acquired.
        """
        lock_key = LOCK_KEY.format(symbol=symbol)
        lock_data = await self.redis.get(lock_key)

        if not lock_data:
            return False  # No lock to recover

        data = json.loads(lock_data)
        lock_age = time.time() - data.get("acquired_at", 0)
        owner_instance = data.get("instance_id")

        should_recover = False
        reason = ""

        # Check if lock is stale by age
        if lock_age > LOCK_STALE_THRESHOLD:
            should_recover = True
            reason = f"age={lock_age:.0f}s exceeds threshold"

        # Check if owning instance is still alive via heartbeat
        if not should_recover and owner_instance:
            heartbeat_key = HEARTBEAT_KEY.format(instance_id=owner_instance)
            if not await self.redis.exists(heartbeat_key):
                should_recover = True
                reason = f"owner {owner_instance} heartbeat missing"

        if should_recover:
            logger.warning(f"Recovering stale lock for {symbol}: {reason}")
            metrics.increment("stale_locks_recovered", tags={"symbol": symbol, "reason": reason})

            # Atomic delete-and-acquire using Lua script
            lua_script = """
            local current = redis.call('GET', KEYS[1])
            if current then
                local data = cjson.decode(current)
                if data.instance_id == ARGV[2] then
                    redis.call('DEL', KEYS[1])
                end
            end
            return redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[3])
            """
            result = await self.redis.eval(
                lua_script,
                keys=[lock_key],
                args=[
                    json.dumps({"instance_id": self.instance_id, "acquired_at": time.time()}),
                    owner_instance,
                    LOCK_TTL
                ]
            )
            return result is not None

        return False
```

### Lock Manager with Stale Recovery

```python
class LockManager:
    def __init__(self, redis_url: str, instance_id: str):
        self.redis = Redis.from_url(redis_url)
        self.instance_id = instance_id
        self.stale_recovery = StaleLockRecovery(self.redis, instance_id)

    async def acquire(self, symbol: str) -> bool:
        """Try to acquire lock, recovering stale locks if needed."""
        # First try normal acquisition
        if await acquire_lock(symbol, self.instance_id):
            return True

        # If normal acquisition failed, check for stale lock
        if await self.stale_recovery.check_and_recover_stale_lock(symbol):
            return True

        return False

    async def release(self, symbol: str):
        """Release lock if we own it."""
        await release_lock(symbol, self.instance_id)
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

| Scenario                     | Behavior                                 |
| ---------------------------- | ---------------------------------------- |
| Previous run still active    | Skip locked symbols, log warning         |
| Single slow symbol           | Continue with others, timeout slow one   |
| All symbols slow             | Partial results published, metrics alert |
| Redis unavailable            | Circuit breaker trips, skip cycle        |
| Process crash with held lock | Heartbeat expires, stale lock recovered  |

## Adaptive Frequency Mechanisms

To handle variable LLM latency and prevent overruns during high-latency periods:

### Latency Tracking

```python
class LatencyTracker:
    def __init__(self, window_size: int = 10):
        self.latencies: deque[float] = deque(maxlen=window_size)
        self.p95_threshold_ms = 8000  # 8 seconds (80% of 10s timeout)
        self.p99_threshold_ms = 9000  # 9 seconds

    def record(self, latency_ms: float):
        """Record a latency measurement."""
        self.latencies.append(latency_ms)
        metrics.histogram("llm_latency_ms", latency_ms)

    def get_p95(self) -> float:
        """Get 95th percentile latency."""
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    def get_p99(self) -> float:
        """Get 99th percentile latency."""
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    def is_high_latency(self) -> bool:
        """Check if we're in a high-latency period."""
        return self.get_p95() > self.p95_threshold_ms
```

### Adaptive Batch Size

```python
class AdaptiveScheduler:
    def __init__(self, config):
        self.config = config
        self.latency_tracker = LatencyTracker()
        self.base_batch_size = config.parallel.max_concurrent
        self.min_batch_size = 3
        self.base_timeout = config.timeouts.symbol_timeout_seconds

    def get_adaptive_batch_size(self) -> int:
        """Reduce batch size during high-latency periods."""
        if self.latency_tracker.is_high_latency():
            # Halve batch size during high latency
            reduced = max(self.min_batch_size, self.base_batch_size // 2)
            logger.info(f"High latency detected, reducing batch size to {reduced}")
            metrics.gauge("adaptive_batch_size", reduced)
            return reduced
        return self.base_batch_size

    def get_adaptive_timeout(self) -> float:
        """Extend timeout during high-latency periods."""
        p95 = self.latency_tracker.get_p95()
        if p95 > self.p95_threshold_ms:
            # Add 50% buffer to P95 latency
            extended = min(self.base_timeout * 1.5, 15.0)  # Cap at 15s
            logger.info(f"Extending timeout to {extended}s based on P95={p95}ms")
            return extended
        return self.base_timeout

    def should_skip_cycle(self) -> bool:
        """Skip cycle if system is severely degraded."""
        p99 = self.latency_tracker.get_p99()
        if p99 > self.p99_threshold_ms:
            logger.warning(f"P99 latency {p99}ms exceeds threshold, skipping cycle")
            metrics.increment("cycles_skipped_high_latency")
            return True
        return False
```

### Backpressure Handling

```python
class BackpressureController:
    def __init__(self):
        self.consecutive_overruns = 0
        self.max_consecutive_overruns = 3
        self.cooldown_cycles = 0
        self.cooldown_period = 2  # Skip 2 cycles after max overruns

    def on_cycle_complete(self, had_overrun: bool, duration_seconds: float):
        """Track cycle completion and detect backpressure."""
        if had_overrun or duration_seconds > 55:  # Near timeout
            self.consecutive_overruns += 1
            if self.consecutive_overruns >= self.max_consecutive_overruns:
                logger.warning(f"Backpressure detected: {self.consecutive_overruns} consecutive overruns")
                self.cooldown_cycles = self.cooldown_period
                metrics.increment("backpressure_cooldowns")
        else:
            self.consecutive_overruns = 0

    def should_run_cycle(self) -> bool:
        """Check if we should run this cycle or cooldown."""
        if self.cooldown_cycles > 0:
            self.cooldown_cycles -= 1
            logger.info(f"Cooling down, {self.cooldown_cycles} cycles remaining")
            return False
        return True
```

## Rate Limit Management

### OpenRouter Limits

```python
# Default OpenRouter rate: ~100 requests/minute
# 20 symbols x 4 tool calls each = 80 requests/minute (within limit)

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
    batch_size = adaptive_scheduler.get_adaptive_batch_size()
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
  schedule: "*/1 * * * *" # Every minute
  timezone: "UTC"
  instance_id: "${HOSTNAME:-runner-1}" # Unique instance identifier
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
    min_concurrent: 3 # Minimum batch size during high latency
    batch_delay_ms: 1000
  timeouts:
    symbol_timeout_seconds: 10
    symbol_timeout_max_seconds: 15 # Extended timeout during high latency
    total_timeout_seconds: 50
  locks:
    ttl_seconds: 90
    stale_threshold_seconds: 120
    redis_key_prefix: "signal:lock:"
  heartbeat:
    ttl_seconds: 30
    interval_seconds: 10
  retry:
    max_attempts: 2
    delay_seconds: 5
  circuit_breaker:
    llm_service:
      failure_threshold: 5
      recovery_timeout_seconds: 60
      half_open_max_calls: 3
      success_threshold: 2
    redis:
      failure_threshold: 3
      recovery_timeout_seconds: 30
  adaptive:
    latency_window_size: 10
    p95_threshold_ms: 8000
    p99_threshold_ms: 9000
    backpressure_max_overruns: 3
    cooldown_cycles: 2
  graceful_shutdown:
    timeout_seconds: 30
    drain_existing: true
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
INSTANCE_ID=runner-1
```

## Implementation

### Main Runner

```python
# services/autonomous_runner/main.py

import asyncio
import logging
import signal
import uuid
from datetime import datetime
from typing import List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Config
from .coordinator import SignalCoordinator
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .adaptive import AdaptiveScheduler, BackpressureController
from .metrics import metrics

logger = logging.getLogger(__name__)

class AutonomousRunner:
    def __init__(self, config: Config):
        self.config = config
        self.instance_id = config.instance_id or str(uuid.uuid4())[:8]
        self.coordinator = SignalCoordinator(config, self.instance_id)
        self.scheduler = AsyncIOScheduler()
        self.adaptive_scheduler = AdaptiveScheduler(config)
        self.backpressure = BackpressureController()
        self.llm_circuit_breaker = CircuitBreaker(
            "llm_service",
            CircuitBreakerConfig(**config.circuit_breaker.llm_service)
        )
        self._shutdown_event = asyncio.Event()
        self._current_cycle_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the autonomous signal generation scheduler."""
        # Start heartbeat for stale lock detection
        await self.coordinator.lock_manager.stale_recovery.start_heartbeat()

        # Register signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

        self.scheduler.add_job(
            self.run_cycle,
            CronTrigger.from_crontab(self.config.schedule),
            id="signal_generation",
            replace_existing=True
        )
        self.scheduler.start()
        logger.info(f"Autonomous runner {self.instance_id} started with schedule: {self.config.schedule}")

        # Wait for shutdown signal
        await self._shutdown_event.wait()

    async def run_cycle(self):
        """Execute one signal generation cycle."""
        # Check backpressure
        if not self.backpressure.should_run_cycle():
            logger.info("Skipping cycle due to backpressure cooldown")
            return

        # Check adaptive scheduler
        if self.adaptive_scheduler.should_skip_cycle():
            return

        # Check circuit breaker
        if not self.llm_circuit_breaker.allow_request():
            logger.warning("Circuit breaker open, skipping cycle")
            metrics.increment("cycles_skipped_circuit_open")
            return

        cycle_start = datetime.utcnow()
        logger.info(f"Starting signal generation cycle at {cycle_start}")
        had_overrun = False

        try:
            self._current_cycle_task = asyncio.current_task()

            # Get adaptive parameters
            batch_size = self.adaptive_scheduler.get_adaptive_batch_size()
            timeout = self.adaptive_scheduler.get_adaptive_timeout()

            signals = await self.coordinator.process_all_symbols(
                self.config.symbols,
                batch_size=batch_size,
                symbol_timeout=timeout
            )

            self.llm_circuit_breaker.on_success()
            metrics.gauge("signals_generated", len(signals))
            logger.info(f"Generated {len(signals)} signals in cycle")

        except asyncio.CancelledError:
            logger.info("Cycle cancelled during shutdown")
            raise
        except CircuitBreakerOpenError:
            logger.warning("Circuit breaker tripped during cycle")
            had_overrun = True
        except Exception as e:
            logger.error(f"Signal generation cycle failed: {e}")
            self.llm_circuit_breaker.on_failure()
            metrics.increment("cycle_failures")
            had_overrun = True

        finally:
            self._current_cycle_task = None
            duration = (datetime.utcnow() - cycle_start).total_seconds()
            metrics.timing("cycle_duration_seconds", duration)
            logger.info(f"Cycle completed in {duration:.2f}s")

            # Track for backpressure
            self.backpressure.on_cycle_complete(had_overrun, duration)

    async def shutdown(self):
        """Graceful shutdown handling."""
        logger.info("Shutdown signal received, initiating graceful shutdown...")

        # Stop accepting new cycles
        self.scheduler.shutdown(wait=False)

        # Wait for current cycle to complete (with timeout)
        if self._current_cycle_task and not self._current_cycle_task.done():
            logger.info("Waiting for current cycle to complete...")
            try:
                await asyncio.wait_for(
                    asyncio.shield(self._current_cycle_task),
                    timeout=self.config.graceful_shutdown.timeout_seconds
                )
                logger.info("Current cycle completed successfully")
            except asyncio.TimeoutError:
                logger.warning("Shutdown timeout, cancelling current cycle")
                self._current_cycle_task.cancel()
                try:
                    await self._current_cycle_task
                except asyncio.CancelledError:
                    pass

        # Release any held locks
        await self.coordinator.release_all_locks()

        # Stop heartbeat
        await self.coordinator.lock_manager.stale_recovery.stop_heartbeat()

        logger.info("Graceful shutdown complete")
        self._shutdown_event.set()

    async def stop(self):
        """Stop the scheduler gracefully (legacy method)."""
        await self.shutdown()
```

### Coordinator

```python
# services/autonomous_runner/coordinator.py

import asyncio
from typing import List, Optional, Set

from .lock_manager import LockManager
from .opencode_client import OpenCodeClient
from .redis_publisher import RedisPublisher
from .adaptive import LatencyTracker

class SignalCoordinator:
    def __init__(self, config, instance_id: str):
        self.config = config
        self.instance_id = instance_id
        self.lock_manager = LockManager(config.redis_url, instance_id)
        self.opencode = OpenCodeClient(config)
        self.publisher = RedisPublisher(config.redis_url)
        self.latency_tracker = LatencyTracker()
        self._held_locks: Set[str] = set()

    async def process_all_symbols(
        self,
        symbols: List[str],
        batch_size: int = None,
        symbol_timeout: float = None
    ) -> List[Signal]:
        """Process all symbols in parallel batches."""
        batch_size = batch_size or self.config.parallel.max_concurrent
        symbol_timeout = symbol_timeout or self.config.timeouts.symbol_timeout_seconds

        results = []

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            batch_results = await self._process_batch(batch, symbol_timeout)
            results.extend(batch_results)

            if i + batch_size < len(symbols):
                await asyncio.sleep(self.config.parallel.batch_delay_ms / 1000)

        # Publish all signals
        for signal in results:
            await self.publisher.publish("channel:raw-signals", signal)

        return results

    async def _process_batch(self, symbols: List[str], timeout: float) -> List[Signal]:
        """Process a batch of symbols in parallel."""
        tasks = [self._process_symbol(s, timeout) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        signals = []
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to process {symbol}: {result}")
            elif result:
                signals.append(result)

        return signals

    async def _process_symbol(self, symbol: str, timeout: float) -> Optional[Signal]:
        """Process a single symbol with lock protection."""
        if not await self.lock_manager.acquire(symbol):
            logger.warning(f"Symbol {symbol} locked, skipping")
            return None

        self._held_locks.add(symbol)
        start_time = time.time()

        try:
            signal = await asyncio.wait_for(
                self.opencode.analyze_symbol(symbol),
                timeout=timeout
            )

            # Record latency for adaptive scheduling
            latency_ms = (time.time() - start_time) * 1000
            self.latency_tracker.record(latency_ms)

            return signal
        except asyncio.TimeoutError:
            logger.warning(f"Timeout processing {symbol}")
            return None
        finally:
            await self.lock_manager.release(symbol)
            self._held_locks.discard(symbol)

    async def release_all_locks(self):
        """Release all locks held by this coordinator (for graceful shutdown)."""
        for symbol in list(self._held_locks):
            try:
                await self.lock_manager.release(symbol)
                self._held_locks.discard(symbol)
            except Exception as e:
                logger.error(f"Failed to release lock for {symbol}: {e}")
```

## Metrics and Monitoring

### Prometheus Metrics

```python
# Counters
signal_generation_total{symbol, action}
signal_generation_skipped{symbol, reason}
cycle_failures_total
cycles_skipped_circuit_open
cycles_skipped_high_latency
stale_locks_recovered{symbol, reason}
circuit_breaker_rejected{breaker}
backpressure_cooldowns

# Gauges
signals_generated_last_cycle
active_locks
symbols_processing
circuit_breaker_state{breaker, state}  # 0=closed, 0.5=half_open, 1=open
adaptive_batch_size
current_p95_latency_ms

# Histograms
cycle_duration_seconds
symbol_processing_duration_seconds{symbol}
llm_latency_ms
```

### Health Endpoints

```python
@app.get("/health")
async def health():
    """Basic health check for load balancer."""
    return {
        "status": "healthy",
        "instance_id": instance_id,
        "uptime_seconds": get_uptime()
    }

@app.get("/health/live")
async def liveness():
    """Kubernetes liveness probe - is the process alive?"""
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness():
    """Kubernetes readiness probe - can we accept traffic?"""
    checks = {
        "redis_connected": await redis.ping(),
        "circuit_breaker_closed": llm_circuit_breaker.state == CircuitState.CLOSED,
        "not_in_cooldown": backpressure.cooldown_cycles == 0
    }

    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503

    return JSONResponse(
        content={
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks
        },
        status_code=status_code
    )

@app.get("/health/detailed")
async def detailed_health():
    """Detailed health status for monitoring dashboards."""
    return {
        "status": "healthy",
        "instance_id": instance_id,
        "last_cycle": last_cycle_time.isoformat() if last_cycle_time else None,
        "last_cycle_duration_seconds": last_cycle_duration,
        "signals_last_cycle": signals_count,
        "active_locks": await lock_manager.count_active(),
        "circuit_breakers": {
            "llm_service": {
                "state": llm_circuit_breaker.state.value,
                "failure_count": llm_circuit_breaker.failure_count,
                "last_failure": llm_circuit_breaker.last_failure_time.isoformat() if llm_circuit_breaker.last_failure_time else None
            }
        },
        "adaptive": {
            "current_batch_size": adaptive_scheduler.get_adaptive_batch_size(),
            "current_timeout": adaptive_scheduler.get_adaptive_timeout(),
            "p95_latency_ms": latency_tracker.get_p95(),
            "high_latency_mode": latency_tracker.is_high_latency()
        },
        "backpressure": {
            "consecutive_overruns": backpressure.consecutive_overruns,
            "cooldown_cycles_remaining": backpressure.cooldown_cycles
        },
        "redis_connected": await redis.ping(),
        "uptime_seconds": get_uptime()
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
          description: "Instance {{ $labels.instance }} last ran {{ $value }}s ago"

      - alert: HighSkipRate
        expr: rate(signal_generation_skipped_total[5m]) > 0.3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "More than 30% of symbols being skipped"

      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state{state="open"} == 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Circuit breaker {{ $labels.breaker }} is open"
          description: "LLM service may be degraded, signal generation paused"

      - alert: HighLatencyMode
        expr: current_p95_latency_ms > 8000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High LLM latency detected"
          description: "P95 latency is {{ $value }}ms, batch size reduced"

      - alert: BackpressureCooldown
        expr: increase(backpressure_cooldowns[10m]) > 2
        labels:
          severity: warning
        annotations:
          summary: "Frequent backpressure cooldowns detected"
          description: "System is struggling to keep up with 1-minute cycles"

      - alert: StaleLockRecoveryHigh
        expr: rate(stale_locks_recovered[15m]) > 0.1
        labels:
          severity: warning
        annotations:
          summary: "High rate of stale lock recovery"
          description: "May indicate process crashes or network issues"

      - alert: CycleFailureRateHigh
        expr: rate(cycle_failures_total[15m]) > 0.2
        labels:
          severity: critical
        annotations:
          summary: "High cycle failure rate"
          description: "More than 20% of cycles failing in last 15 minutes"
```

### Alerting Thresholds Summary

| Metric               | Warning     | Critical          |
| -------------------- | ----------- | ----------------- |
| Cycle delay          | > 2 minutes | > 5 minutes       |
| Skip rate            | > 30%       | > 50%             |
| Circuit breaker open | -           | Any duration > 1m |
| P95 latency          | > 8000ms    | > 12000ms         |
| Cycle failure rate   | > 10%       | > 20%             |
| Stale lock recovery  | > 0.1/min   | > 0.5/min         |

## Deployment

### Kubernetes CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: signal-generator
spec:
  schedule: "*/1 * * * *"
  concurrencyPolicy: Forbid # Don't run if previous still running
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      activeDeadlineSeconds: 55 # Kill if takes too long
      template:
        spec:
          restartPolicy: Never
          terminationGracePeriodSeconds: 35 # Allow graceful shutdown
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
                - name: INSTANCE_ID
                  valueFrom:
                    fieldRef:
                      fieldPath: metadata.name
              resources:
                requests:
                  memory: "512Mi"
                  cpu: "250m"
                limits:
                  memory: "1Gi"
                  cpu: "500m"
              livenessProbe:
                httpGet:
                  path: /health/live
                  port: 8080
                initialDelaySeconds: 5
                periodSeconds: 10
              readinessProbe:
                httpGet:
                  path: /health/ready
                  port: 8080
                initialDelaySeconds: 5
                periodSeconds: 5
```

### Alternative: Long-Running Service

For lower latency, run as a long-running service with internal scheduler:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: autonomous-runner
spec:
  replicas: 1 # Single instance to avoid duplicate runs
  selector:
    matchLabels:
      app: autonomous-runner
  template:
    metadata:
      labels:
        app: autonomous-runner
    spec:
      terminationGracePeriodSeconds: 35
      containers:
        - name: runner
          image: tradestream/autonomous-runner:latest
          command: ["python", "-m", "autonomous_runner.main", "--mode=service"]
          env:
            - name: INSTANCE_ID
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
          ports:
            - containerPort: 8080
              name: http
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
          lifecycle:
            preStop:
              httpGet:
                path: /shutdown
                port: 8080
```

## Constraints

- Must complete 20 symbols in < 50 seconds (10s buffer before next cycle)
- Must not exceed OpenRouter rate limits (~100 req/min)
- Graceful degradation if LLM unavailable (circuit breaker opens, skip cycle, alert)
- Signals timestamped for deduplication
- Dashboard shows signals even with no users connected
- Single instance running (no duplicate cycles)
- Graceful shutdown must complete within 30 seconds
- Stale locks must be recovered within 2 minutes of process crash

## Acceptance Criteria

- [ ] Signals generated for 20 symbols every 1 minute
- [ ] Parallel processing via batched subagent invocation
- [ ] Overrun protection with Redis locks
- [ ] Stale lock recovery via heartbeat mechanism
- [ ] Circuit breaker prevents cascading failures
- [ ] Adaptive batch size during high latency periods
- [ ] Failed symbols logged but don't block others
- [ ] Dashboard shows signals even with no users connected
- [ ] Metrics: processing time per symbol, success rate, circuit breaker state
- [ ] Health endpoints (liveness, readiness, detailed)
- [ ] Alerts fire on failures, delays, circuit breaker events
- [ ] Graceful shutdown completes in-flight work

## File Structure

```
services/autonomous_runner/
|-- __init__.py
|-- main.py                  # Entry point with graceful shutdown
|-- config.py                # Configuration loading
|-- coordinator.py           # Signal coordination logic
|-- lock_manager.py          # Redis lock management with stale recovery
|-- circuit_breaker.py       # Circuit breaker implementation
|-- adaptive.py              # Adaptive scheduling and backpressure
|-- opencode_client.py       # OpenCode invocation
|-- redis_publisher.py       # Redis pub/sub
|-- metrics.py               # Prometheus metrics
|-- health.py                # Health check endpoints
|-- requirements.txt
|-- Dockerfile
|-- tests/
    |-- test_coordinator.py
    |-- test_lock_manager.py
    |-- test_circuit_breaker.py
    |-- test_adaptive.py
```
