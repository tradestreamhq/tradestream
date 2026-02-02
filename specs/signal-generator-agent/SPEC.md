# Signal Generator Agent Specification

## Goal

OpenCode agent that analyzes trading symbols and generates raw BUY/SELL/HOLD signals with confidence scores and strategy breakdowns.

## Target Behavior

The Signal Generator Agent is the first stage in the signal pipeline. It runs every 1 minute for each active symbol (in parallel), uses MCP tools to gather strategy and market data, and outputs raw signals for downstream processing.

### Signal Output Format

```json
{
  "signal_id": "sig-abc123",
  "symbol": "ETH/USD",
  "action": "BUY",
  "confidence": 0.82,
  "strategies_analyzed": 5,
  "strategies_bullish": 4,
  "strategies_bearish": 1,
  "strategies_neutral": 0,
  "top_strategy": {
    "name": "RSI_REVERSAL",
    "score": 0.89,
    "signal": "BUY",
    "parameters": {
      "rsiPeriod": 14,
      "oversold": 30
    }
  },
  "strategy_breakdown": [
    {"name": "RSI_REVERSAL", "signal": "BUY", "score": 0.89},
    {"name": "MACD_CROSS", "signal": "BUY", "score": 0.85},
    {"name": "BOLLINGER_BOUNCE", "signal": "BUY", "score": 0.78},
    {"name": "EMA_TREND", "signal": "BUY", "score": 0.72},
    {"name": "VOLUME_BREAKOUT", "signal": "SELL", "score": 0.65}
  ],
  "reasoning": "Strong consensus among top strategies. RSI shows oversold recovery at 28, MACD just crossed bullish with histogram expanding. 4 of 5 top strategies signal BUY.",
  "market_context": {
    "current_price": 2450.50,
    "price_change_1h": 0.023,
    "volume_ratio": 1.45,
    "volatility_1h": 0.018
  },
  "timestamp": "2025-02-01T12:34:56Z"
}
```

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  SIGNAL GENERATOR AGENT (OpenCode)                         │
│                                                             │
│  System Prompt:                                             │
│  "You are a trading signal analyst. Analyze symbols using  │
│   available tools and generate BUY/SELL/HOLD signals."     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ MCP Servers                                          │   │
│  │  • strategy-mcp: get_top_strategies, get_signals    │   │
│  │  • market-data-mcp: get_candles, get_current_price  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Skills                                               │   │
│  │  • analyze-symbol: Full symbol analysis workflow     │   │
│  │  • detect-patterns: Pattern recognition prompts      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Output: Raw signal → Redis channel:raw-signals            │
└─────────────────────────────────────────────────────────────┘
```

### Analysis Workflow

1. **Fetch Top Strategies**: Call `get_top_strategies(symbol, limit=5)` to get highest-performing strategies for this symbol
2. **Get Strategy Signals**: For each strategy, call `get_strategy_signal(strategy_id, symbol)` to get current signal
3. **Get Market Context**: Call `get_current_price(symbol)` and `get_volatility(symbol, timeframe="1h")`
4. **Synthesize Signal**:
   - Count bullish/bearish/neutral signals
   - Calculate confidence based on consensus strength
   - Generate reasoning explaining the decision
5. **Publish Signal**: Send to Redis `channel:raw-signals`

### Confidence Calculation

```python
def calculate_confidence(strategies: list[StrategySignal]) -> float:
    """
    Confidence based on strategy consensus and individual scores.

    - 5/5 agree: 0.90-0.95 (modified by avg strategy score)
    - 4/5 agree: 0.75-0.85
    - 3/5 agree: 0.60-0.70
    - 2/5 agree: 0.45-0.55
    - 1/5 agree: 0.30-0.40
    """
    bullish = sum(1 for s in strategies if s.signal == "BUY")
    bearish = sum(1 for s in strategies if s.signal == "SELL")
    total = len(strategies)

    max_agreement = max(bullish, bearish, total - bullish - bearish)
    consensus_ratio = max_agreement / total

    avg_score = sum(s.score for s in strategies) / total

    # Base confidence from consensus
    if consensus_ratio >= 0.8:
        base = 0.85
    elif consensus_ratio >= 0.6:
        base = 0.70
    else:
        base = 0.50

    # Adjust by average strategy score
    confidence = base * (0.8 + 0.2 * avg_score)

    return min(0.95, max(0.30, confidence))
```

## Parallelization Strategy

### Concurrency Configuration

```python
PARALLEL_CONFIG = {
    "max_concurrent_symbols": 10,        # Max symbols processed simultaneously
    "thread_pool_size": 20,              # asyncio thread pool for blocking I/O
    "batch_size": 10,                    # Symbols per batch
    "inter_batch_delay_ms": 1000,        # Delay between batches to respect rate limits
}
```

### Rationale

- **10 concurrent symbols**: Balances throughput (20 symbols / min) against OpenRouter rate limits (~100 req/min). With 8-9 tool calls per symbol, 10 concurrent = ~90 requests in flight.
- **20-thread pool**: Provides headroom for I/O-bound MCP tool calls without overwhelming system resources.
- **Batch processing**: Enables graceful degradation if one batch fails; isolates failures.

### Implementation

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class ParallelProcessor:
    def __init__(self, config: dict):
        self.semaphore = asyncio.Semaphore(config["max_concurrent_symbols"])
        self.executor = ThreadPoolExecutor(max_workers=config["thread_pool_size"])

    async def process_with_limit(self, symbol: str) -> Optional[Signal]:
        """Process symbol with concurrency limiting."""
        async with self.semaphore:
            return await self._process_symbol(symbol)

    async def process_batch_parallel(self, symbols: list[str]) -> BatchResult:
        """Process all symbols with controlled parallelism."""
        tasks = [self.process_with_limit(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = []
        failed = []
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                failed.append({"symbol": symbol, "error": str(result)})
            elif result:
                successful.append(result)

        return BatchResult(successful=successful, failed=failed)
```

## Caching Strategy

### Cache Configuration

```python
CACHE_CONFIG = {
    # Data type TTLs
    "strategy_list_ttl_seconds": 300,      # 5 min - top strategies change slowly
    "strategy_signal_ttl_seconds": 60,     # 1 min - signals refresh each cycle
    "market_price_ttl_seconds": 10,        # 10 sec - prices are near-realtime
    "volatility_ttl_seconds": 60,          # 1 min - volatility recalculated

    # Degraded mode TTLs (used when MCP tools fail)
    "degraded_mode_strategy_ttl_seconds": 600,   # 10 min fallback for strategies
    "degraded_mode_price_ttl_seconds": 120,      # 2 min fallback for prices

    # Cache backend
    "backend": "redis",
    "redis_key_prefix": "signal-gen:cache:",
    "local_fallback_enabled": True,        # In-memory fallback if Redis fails
}
```

### Cache Implementation

```python
from datetime import datetime, timedelta
from typing import Optional, Any

class SignalCache:
    def __init__(self, redis_client, config: dict):
        self.redis = redis_client
        self.config = config
        self.local_cache = {}  # In-memory fallback

    async def get_strategies(self, symbol: str) -> Optional[list]:
        """Get cached strategy list with TTL check."""
        return await self._get(
            f"strategies:{symbol}",
            self.config["strategy_list_ttl_seconds"]
        )

    async def get_strategy_signal(self, strategy_id: str, symbol: str) -> Optional[dict]:
        """Get cached strategy signal."""
        return await self._get(
            f"signal:{strategy_id}:{symbol}",
            self.config["strategy_signal_ttl_seconds"]
        )

    async def get_degraded_strategies(self, symbol: str) -> Optional[list]:
        """Get longer-lived cached strategies for degraded mode."""
        return await self._get(
            f"degraded:strategies:{symbol}",
            self.config["degraded_mode_strategy_ttl_seconds"]
        )

    async def set_with_ttl(self, key: str, value: Any, ttl_seconds: int):
        """Cache data with explicit TTL."""
        full_key = f"{self.config['redis_key_prefix']}{key}"
        payload = {
            "value": value,
            "cached_at": datetime.utcnow().isoformat()
        }
        try:
            await self.redis.setex(full_key, ttl_seconds, json.dumps(payload))
        except Exception:
            if self.config["local_fallback_enabled"]:
                self.local_cache[full_key] = payload

    async def _get(self, key: str, max_age_seconds: int) -> Optional[Any]:
        """Get from cache if within TTL."""
        full_key = f"{self.config['redis_key_prefix']}{key}"
        try:
            data = await self.redis.get(full_key)
            if data:
                payload = json.loads(data)
                cached_at = datetime.fromisoformat(payload["cached_at"])
                if datetime.utcnow() - cached_at < timedelta(seconds=max_age_seconds):
                    return payload["value"]
        except Exception:
            if self.config["local_fallback_enabled"]:
                return self.local_cache.get(full_key, {}).get("value")
        return None
```

## Model Requirements

### Required Capabilities

```python
MODEL_CONFIG = {
    "required_capabilities": ["tool_calling"],
    "recommended_capabilities": ["structured_output", "json_mode"],
    "recommended_models": [
        "anthropic/claude-sonnet-4-20250514",
        "openai/gpt-4o",
        "google/gemini-2.0-flash",
    ],
    "fallback_model": "anthropic/claude-sonnet-4-20250514",
    "min_context_window": 8000,
}
```

### Model Validation

The agent validates model capabilities at startup and handles incompatible models:

```python
class ModelValidator:
    def __init__(self, openrouter_client, config: dict):
        self.client = openrouter_client
        self.config = config

    async def validate_model(self, model_id: str) -> ModelValidation:
        """Check if model supports required capabilities."""
        try:
            model_info = await self.client.get_model_info(model_id)
            capabilities = model_info.get("capabilities", [])

            has_tool_calling = "tool_calling" in capabilities
            has_structured = "structured_output" in capabilities

            return ModelValidation(
                valid=has_tool_calling,
                has_tool_calling=has_tool_calling,
                has_structured_output=has_structured,
                warnings=[] if has_tool_calling else ["Model lacks tool_calling"]
            )
        except Exception as e:
            return ModelValidation(valid=False, error=str(e))

    async def get_valid_model(self, preferred_model: str) -> str:
        """Get a valid model, falling back if necessary."""
        validation = await self.validate_model(preferred_model)

        if validation.valid:
            return preferred_model

        logger.warning(
            f"Model {preferred_model} doesn't support tool calling, "
            f"falling back to {self.config['fallback_model']}"
        )
        metrics.increment("model_fallback_total", tags={"from": preferred_model})
        return self.config["fallback_model"]
```

### Non-Tool-Calling Model Behavior

When a configured model doesn't support tool calling:

1. **Startup validation**: Agent validates model before first invocation
2. **Automatic fallback**: Switches to `fallback_model` (Claude Sonnet)
3. **Warning logged**: Operator visibility into fallback events
4. **Metric emitted**: `model_fallback_total` tracks fallback frequency
5. **No silent failures**: Agent refuses to run without a tool-capable model

## MCP Tool Retry Strategy

### Retry Configuration

```python
RETRY_CONFIG = {
    "max_attempts": 3,                    # Total attempts (1 initial + 2 retries)
    "initial_delay_ms": 500,              # First retry delay
    "max_delay_ms": 5000,                 # Maximum backoff delay
    "backoff_multiplier": 2.0,            # Exponential backoff factor
    "jitter_factor": 0.1,                 # Random jitter (0-10% of delay)
    "retryable_errors": [
        "TIMEOUT",
        "CONNECTION_ERROR",
        "RATE_LIMITED",
        "SERVER_ERROR",
    ],
    "non_retryable_errors": [
        "INVALID_PARAMETERS",
        "NOT_FOUND",
        "UNAUTHORIZED",
    ],
}
```

### Retry Implementation

```python
import asyncio
import random
from typing import TypeVar, Callable, Awaitable

T = TypeVar("T")

class MCPRetryHandler:
    def __init__(self, config: dict):
        self.config = config

    async def with_retry(
        self,
        tool_name: str,
        operation: Callable[[], Awaitable[T]]
    ) -> T:
        """Execute MCP tool call with exponential backoff retry."""
        last_error = None
        delay_ms = self.config["initial_delay_ms"]

        for attempt in range(self.config["max_attempts"]):
            try:
                return await operation()
            except Exception as e:
                error_type = self._classify_error(e)
                last_error = e

                if error_type in self.config["non_retryable_errors"]:
                    logger.error(f"Non-retryable error for {tool_name}: {e}")
                    raise

                if attempt < self.config["max_attempts"] - 1:
                    jitter = random.uniform(0, self.config["jitter_factor"] * delay_ms)
                    wait_time = min(delay_ms + jitter, self.config["max_delay_ms"])

                    logger.warning(
                        f"Retry {attempt + 1}/{self.config['max_attempts']} "
                        f"for {tool_name} after {wait_time:.0f}ms: {e}"
                    )
                    metrics.increment("mcp_retry_total", tags={
                        "tool": tool_name,
                        "attempt": attempt + 1
                    })

                    await asyncio.sleep(wait_time / 1000)
                    delay_ms *= self.config["backoff_multiplier"]

        # All retries exhausted
        metrics.increment("mcp_retry_exhausted_total", tags={"tool": tool_name})
        raise last_error

    def _classify_error(self, error: Exception) -> str:
        """Classify error for retry decision."""
        error_str = str(error).lower()
        if "timeout" in error_str:
            return "TIMEOUT"
        if "connection" in error_str or "network" in error_str:
            return "CONNECTION_ERROR"
        if "rate" in error_str or "429" in error_str:
            return "RATE_LIMITED"
        if "500" in error_str or "502" in error_str or "503" in error_str:
            return "SERVER_ERROR"
        if "invalid" in error_str or "parameter" in error_str:
            return "INVALID_PARAMETERS"
        if "not found" in error_str or "404" in error_str:
            return "NOT_FOUND"
        if "unauthorized" in error_str or "401" in error_str:
            return "UNAUTHORIZED"
        return "UNKNOWN"
```

## Batch Processing Error Handling

### Partial Failure Strategy

When processing multiple symbols, partial failures are handled gracefully:

```python
@dataclass
class BatchResult:
    successful: list[Signal]
    failed: list[FailedSymbol]
    partial: list[PartialSignal]  # Signals with degraded data

    @property
    def success_rate(self) -> float:
        total = len(self.successful) + len(self.failed) + len(self.partial)
        return (len(self.successful) + len(self.partial)) / total if total > 0 else 0

@dataclass
class FailedSymbol:
    symbol: str
    error: str
    error_type: str
    retries_attempted: int

@dataclass
class PartialSignal:
    signal: Signal
    missing_data: list[str]  # e.g., ["market_context", "volatility"]
    confidence_penalty: float  # Applied reduction to confidence

class BatchProcessor:
    async def process_batch(self, symbols: list[str]) -> BatchResult:
        """Process batch with partial failure handling."""
        tasks = [self._process_symbol_safe(s) for s in symbols]
        results = await asyncio.gather(*tasks)

        successful = []
        failed = []
        partial = []

        for symbol, result in zip(symbols, results):
            if result.is_success:
                successful.append(result.signal)
            elif result.is_partial:
                partial.append(PartialSignal(
                    signal=result.signal,
                    missing_data=result.missing_data,
                    confidence_penalty=result.confidence_penalty
                ))
            else:
                failed.append(FailedSymbol(
                    symbol=symbol,
                    error=result.error,
                    error_type=result.error_type,
                    retries_attempted=result.retries
                ))

        batch_result = BatchResult(successful, failed, partial)

        # Log and emit metrics
        logger.info(
            f"Batch complete: {len(successful)} success, "
            f"{len(partial)} partial, {len(failed)} failed"
        )
        metrics.gauge("batch_success_rate", batch_result.success_rate)

        # Alert if too many failures
        if batch_result.success_rate < 0.5:
            logger.error(f"Batch failure rate critical: {1 - batch_result.success_rate:.1%}")
            metrics.increment("batch_critical_failure")

        return batch_result

    async def _process_symbol_safe(self, symbol: str) -> ProcessResult:
        """Process symbol, catching errors and returning structured result."""
        try:
            signal = await self._process_symbol(symbol)
            return ProcessResult(is_success=True, signal=signal)
        except PartialDataError as e:
            # Some tools failed but we have enough data for a degraded signal
            signal = await self._generate_degraded_signal(symbol, e.available_data)
            signal.confidence *= (1 - e.confidence_penalty)
            return ProcessResult(
                is_success=False,
                is_partial=True,
                signal=signal,
                missing_data=e.missing_tools,
                confidence_penalty=e.confidence_penalty
            )
        except Exception as e:
            return ProcessResult(
                is_success=False,
                error=str(e),
                error_type=type(e).__name__,
                retries=self.retry_handler.config["max_attempts"]
            )
```

### Degraded Signal Generation

When some MCP tools fail but others succeed:

```python
async def _generate_degraded_signal(
    self,
    symbol: str,
    available_data: dict
) -> Signal:
    """Generate signal with incomplete data."""
    # Calculate confidence penalty based on missing data
    penalties = {
        "strategies": 0.20,      # Critical - 20% penalty
        "market_context": 0.10,  # Important - 10% penalty
        "volatility": 0.05,      # Nice-to-have - 5% penalty
    }

    total_penalty = sum(
        penalties.get(tool, 0.05)
        for tool in available_data.get("missing_tools", [])
    )

    signal = Signal(
        symbol=symbol,
        action=self._determine_action(available_data),
        confidence=max(0.30, 0.70 - total_penalty),  # Base 0.70, min 0.30
        reasoning=f"Degraded signal due to unavailable tools: {available_data['missing_tools']}",
        is_degraded=True
    )

    return signal
```

## MCP Tools Used

### strategy-mcp

| Tool | Parameters | Returns |
|------|------------|---------|
| `get_top_strategies` | `symbol: string, limit: int` | Array of top strategies with scores |
| `get_strategy_signal` | `strategy_id: string, symbol: string` | Current signal for strategy |
| `get_strategy_consensus` | `symbol: string` | Aggregated consensus across all strategies |

### market-data-mcp

| Tool | Parameters | Returns |
|------|------------|---------|
| `get_current_price` | `symbol: string` | Current price and 24h change |
| `get_candles` | `symbol: string, timeframe: string, limit: int` | OHLCV candles |
| `get_volatility` | `symbol: string, timeframe: string` | Volatility metrics |

## Skills

### analyze-symbol

```markdown
# Skill: analyze-symbol

## Purpose
Perform comprehensive analysis of a trading symbol using available MCP tools.

## Workflow
1. Fetch top 5 strategies for the symbol
2. Get current signal from each strategy
3. Gather market context (price, volume, volatility)
4. Synthesize findings into a trading signal

## Output Format
Structured JSON signal with confidence and reasoning.
```

### detect-patterns

```markdown
# Skill: detect-patterns

## Purpose
Identify technical patterns in recent price action.

## Patterns to Detect
- Trend: Uptrend, Downtrend, Sideways
- Momentum: Accelerating, Decelerating, Reversal
- Volume: Breakout confirmation, Divergence
- Support/Resistance: Near key levels

## Output
Pattern summary to include in signal reasoning.
```

## Constraints

- Must complete analysis in < 10 seconds per symbol
- Must work with any OpenRouter-supported model that supports tool calling
- Publishes to Redis channel: `channel:raw-signals`
- Signal format must match schema exactly
- Must handle tool failures gracefully (retry, then fallback to cache, then degraded signal)

## Configuration

```json
{
  "name": "signal-generator",
  "model": "google/gemini-2.0-flash",
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
    "max_strategies": 5
  },
  "parallel": {
    "max_concurrent_symbols": 10,
    "thread_pool_size": 20,
    "batch_size": 10,
    "inter_batch_delay_ms": 1000
  },
  "cache": {
    "strategy_list_ttl_seconds": 300,
    "strategy_signal_ttl_seconds": 60,
    "market_price_ttl_seconds": 10,
    "degraded_mode_ttl_seconds": 600
  },
  "retry": {
    "max_attempts": 3,
    "initial_delay_ms": 500,
    "max_delay_ms": 5000,
    "backoff_multiplier": 2.0
  }
}
```

## Acceptance Criteria

- [ ] Agent analyzes symbol using MCP tools (strategy + market data)
- [ ] Raw signal published to Redis within 10 seconds
- [ ] Reasoning includes strategy breakdown with individual signals
- [ ] Works with Claude, GPT-4, Gemini via OpenRouter (any tool-calling model)
- [ ] Validates model supports tool calling; falls back to Claude Sonnet if not
- [ ] Handles tool failures with retry (3 attempts, exponential backoff)
- [ ] Falls back to cached data when tools fail (with defined TTLs)
- [ ] Handles partial failures: publishes degraded signals with reduced confidence
- [ ] Batch processing continues despite individual symbol failures
- [ ] Signal format matches schema exactly
- [ ] Confidence calculation follows defined formula

## File Structure

```
agents/signal-generator/
├── .opencode/
│   └── config.json
├── skills/
│   ├── analyze-symbol/
│   │   └── SKILL.md
│   └── detect-patterns/
│       └── SKILL.md
├── prompts/
│   └── system.md
└── tests/
    └── test_signal_generator.py
```

## Example Invocation

```bash
# Run signal generator for a single symbol
opencode --config agents/signal-generator/.opencode/config.json \
  --prompt "Analyze ETH/USD and generate a trading signal"

# Run for multiple symbols (via Task tool internally)
opencode --config agents/signal-generator/.opencode/config.json \
  --prompt "Analyze these symbols: ETH/USD, BTC/USD, SOL/USD"
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| strategy-mcp unavailable | Retry 3x with backoff, then use cached strategies (5 min TTL), reduce confidence by 20% |
| market-data-mcp unavailable | Retry 3x, then skip market context, note in reasoning, reduce confidence by 10% |
| All tools fail | Retry 3x each, then generate HOLD signal with 0.30 confidence |
| Timeout exceeded | Publish partial signal with available data, log warning |
| Invalid symbol | Return error event, skip symbol, continue batch |
| Model lacks tool calling | Automatic fallback to Claude Sonnet, log warning |
| Rate limited | Exponential backoff with jitter, max 5 second delay |

## Metrics

- `signal_generator_signals_total` - Signals generated by action
- `signal_generator_latency_ms` - Time to generate signal
- `signal_generator_tool_calls_total` - Tool calls by tool name
- `signal_generator_errors_total` - Errors by type
- `signal_generator_confidence_histogram` - Distribution of confidence scores
- `signal_generator_retry_total` - Retry attempts by tool and attempt number
- `signal_generator_retry_exhausted_total` - Retries exhausted by tool
- `signal_generator_cache_hit_total` - Cache hits by data type
- `signal_generator_cache_miss_total` - Cache misses by data type
- `signal_generator_degraded_signals_total` - Degraded signals generated
- `signal_generator_model_fallback_total` - Model fallbacks triggered
- `signal_generator_batch_success_rate` - Success rate per batch
