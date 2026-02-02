# Model Routing Specification

## Goal

Cost-optimized model selection using 2026 state-of-the-art models for tool use, routing tasks to appropriate models based on complexity and importance.

## 2026 Tool Use Benchmark Leaders

Based on Tau2-bench (Telecom) and internal testing:

| Model | Tau2 Score | MCP Support | Best For | Strengths |
|-------|-----------|-------------|----------|-----------|
| **Claude Opus 4.5** | 98.2% | Native | Complex multi-step orchestration | Best-in-class reasoning, handles ambiguity |
| **GPT-5.2 Thinking** | 94.5% | Native | Agentic tasks, knowledge work | Strong chain-of-thought, reliable |
| **Claude Sonnet 4.5** | ~90% | Native | Balanced cost/performance | Great value for complex tasks |
| **Gemini 3.0 Pro** | 85.4% | Native | Speed, multimodal inputs | Fast, good for structured data |
| **Gemini 3.0 Flash** | ~80% | Native | High volume, cost-sensitive | Extremely fast and cheap |

## Pricing (OpenRouter 2026)

| Model | Input/1M tokens | Output/1M tokens | Notes |
|-------|-----------------|------------------|-------|
| **Gemini 3.0 Flash** | $0.10 | $0.40 | Best value for volume |
| **Gemini 3.0 Pro** | $1.25 | $5.00 | Balanced price/perf |
| **GPT-5.2** | $1.75 | $14.00 | Premium reasoning |
| **Claude Sonnet 4.5** | $3.00 | $15.00 | Premium balanced |
| **Claude Opus 4.5** | $15.00 | $75.00 | Mission-critical only |

## Model Routing Strategy

### By Agent Type

```python
MODEL_ROUTING = {
    # High volume, routine tasks → cheapest reliable model
    "signal-generator": "google/gemini-3.0-flash",

    # Needs reasoning about multiple factors → mid-tier
    "opportunity-scorer": "google/gemini-3.0-pro",

    # Critical decisions, escalate based on opportunity score
    "portfolio-advisor": {
        "default": "openai/gpt-5.2",
        "high_opportunity": "anthropic/claude-sonnet-4.5",
        "critical": "anthropic/claude-opus-4.5"
    },

    # Formatting and summarization → cheapest
    "report-generator": "google/gemini-3.0-flash",

    # Complex spec generation → premium reasoning
    "learning": "anthropic/claude-sonnet-4.5",

    # Evaluation with nuance → mid-tier
    "janitor": "google/gemini-3.0-pro"
}
```

### Dynamic Routing for Portfolio Advisor

```python
def select_model_for_portfolio_advisor(opportunity_score: float) -> str:
    """
    Select model based on signal importance.

    Higher opportunity scores warrant more capable (expensive) models
    because the potential upside justifies the cost.
    """
    if opportunity_score >= 85:
        # Critical opportunity: use best-in-class
        # Cost justified by potential trade value
        return "anthropic/claude-opus-4.5"

    if opportunity_score >= 70:
        # High opportunity: use premium
        return "anthropic/claude-sonnet-4.5"

    # Standard opportunity: use reliable mid-tier
    return "openai/gpt-5.2"
```

### Full Routing Implementation

```python
# services/model_router/router.py

from dataclasses import dataclass
from typing import Optional
import asyncio

@dataclass
class ModelSelection:
    model_id: str
    reason: str
    estimated_cost_per_1k_tokens: float

@dataclass
class RetryConfig:
    max_retries: int = 2
    initial_delay_ms: int = 500
    max_delay_ms: int = 5000
    exponential_backoff: bool = True

class ModelRouter:
    def __init__(self, config: dict):
        self.config = config
        # Fallback chain ordered by cost (cheapest first) to minimize
        # cost spikes during outages while maintaining capability
        self.fallback_chain = [
            "google/gemini-3.0-flash",   # $0.10/$0.40 - ultra cheap
            "google/gemini-3.0-pro",     # $1.25/$5.00 - cheap
            "openai/gpt-5.2",            # $1.75/$14.00 - mid-tier
            "anthropic/claude-sonnet-4.5" # $3.00/$15.00 - premium fallback
        ]
        self.retry_config = RetryConfig()

    async def call_with_retry(
        self,
        model_id: str,
        call_fn,
        *args,
        **kwargs
    ):
        """
        Call model with retry logic before falling back.

        Retry policy:
        - Retry up to max_retries times on transient failures
        - Use exponential backoff between retries
        - Only fall back to next model after exhausting retries
        """
        last_error = None
        delay_ms = self.retry_config.initial_delay_ms

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                return await call_fn(model_id, *args, **kwargs)
            except (RateLimitError, ServiceUnavailableError) as e:
                last_error = e
                if attempt < self.retry_config.max_retries:
                    await asyncio.sleep(delay_ms / 1000)
                    if self.retry_config.exponential_backoff:
                        delay_ms = min(delay_ms * 2, self.retry_config.max_delay_ms)
            except ModelUnavailableError as e:
                # Don't retry, go straight to fallback
                last_error = e
                break

        # Retries exhausted, try fallback
        fallback = self.get_fallback(model_id)
        if fallback:
            return await self.call_with_retry(fallback, call_fn, *args, **kwargs)

        raise last_error

    def select_model(
        self,
        agent_type: str,
        opportunity_score: Optional[float] = None,
        complexity: str = "standard"  # simple, standard, complex
    ) -> ModelSelection:
        """Select optimal model for the given context."""

        # Signal Generator: High volume, simple queries
        if agent_type == "signal-generator":
            return ModelSelection(
                model_id="google/gemini-3.0-flash",
                reason="High volume routine analysis",
                estimated_cost_per_1k_tokens=0.0003
            )

        # Opportunity Scorer: Needs some reasoning
        if agent_type == "opportunity-scorer":
            return ModelSelection(
                model_id="google/gemini-3.0-pro",
                reason="Multi-factor scoring requires reasoning",
                estimated_cost_per_1k_tokens=0.003
            )

        # Portfolio Advisor: Escalate based on opportunity
        if agent_type == "portfolio-advisor":
            if opportunity_score and opportunity_score >= 85:
                return ModelSelection(
                    model_id="anthropic/claude-opus-4.5",
                    reason=f"Critical opportunity (score={opportunity_score})",
                    estimated_cost_per_1k_tokens=0.045
                )
            if opportunity_score and opportunity_score >= 70:
                return ModelSelection(
                    model_id="anthropic/claude-sonnet-4.5",
                    reason=f"High opportunity (score={opportunity_score})",
                    estimated_cost_per_1k_tokens=0.009
                )
            return ModelSelection(
                model_id="openai/gpt-5.2",
                reason="Standard portfolio validation",
                estimated_cost_per_1k_tokens=0.008
            )

        # Report Generator: Simple formatting
        if agent_type == "report-generator":
            return ModelSelection(
                model_id="google/gemini-3.0-flash",
                reason="Text formatting and summarization",
                estimated_cost_per_1k_tokens=0.0003
            )

        # Learning Agent: Complex spec generation
        if agent_type == "learning":
            return ModelSelection(
                model_id="anthropic/claude-sonnet-4.5",
                reason="Complex creative generation",
                estimated_cost_per_1k_tokens=0.009
            )

        # Janitor: Nuanced evaluation
        if agent_type == "janitor":
            return ModelSelection(
                model_id="google/gemini-3.0-pro",
                reason="Retirement evaluation requires judgment",
                estimated_cost_per_1k_tokens=0.003
            )

        # Default fallback
        return ModelSelection(
            model_id="google/gemini-3.0-flash",
            reason="Default fallback",
            estimated_cost_per_1k_tokens=0.0003
        )

    def get_fallback(self, failed_model: str) -> Optional[str]:
        """
        Get next model in fallback chain.

        Chain is ordered cheapest-first to minimize cost during outages.
        """
        try:
            idx = self.fallback_chain.index(failed_model)
            if idx + 1 < len(self.fallback_chain):
                return self.fallback_chain[idx + 1]
        except ValueError:
            pass
        return self.fallback_chain[-1] if self.fallback_chain else None
```

## Cost Estimation

### Per-Cycle Cost (1 minute, 20 symbols)

| Agent | Model | Calls | Tokens/call | Cost/cycle |
|-------|-------|-------|-------------|------------|
| Signal Generator | Flash | 20 | ~1,500 | $0.01 |
| Opportunity Scorer | Pro | 20 | ~800 | $0.02 |
| Portfolio Advisor | Mixed | ~5 | ~600 | $0.02 |
| Report Generator | Flash | 20 | ~500 | $0.004 |
| **Total per cycle** | | | | **~$0.05** |

### Monthly Cost Projections

| Frequency | Cycles/day | Cost/day | Cost/month |
|-----------|------------|----------|------------|
| 1 minute | 1,440 | $72 | **$2,160** |
| 5 minutes | 288 | $14.40 | **$432** |
| 15 minutes | 96 | $4.80 | **$144** |

### With Learning/Janitor Agents

| Agent | Frequency | Cost/run | Monthly |
|-------|-----------|----------|---------|
| Learning | 4x/day | $0.50 | $60 |
| Janitor | 1x/day | $0.20 | $6 |

### Total Monthly Budget

| Scenario | Signal Frequency | Total/month |
|----------|------------------|-------------|
| Production (1-min) | Every 1 minute | ~$2,300 |
| Cost-conscious (5-min) | Every 5 minutes | ~$500 |
| Development (15-min) | Every 15 minutes | ~$200 |

## Models to Avoid

| Model | Issue | Alternative |
|-------|-------|-------------|
| DeepSeek V3.x | "Struggles with multi-tool workflows" | Gemini Flash |
| Claude Haiku 3 | Deprecated | Gemini Flash |
| GPT-3.5 Turbo | Poor tool use | Gemini Flash |
| Local LLMs | Inconsistent tool calling | Cloud models |

## Configuration

```yaml
model_routing:
  default_model: "google/gemini-3.0-flash"

  agents:
    signal-generator:
      model: "google/gemini-3.0-flash"
      max_tokens: 2000
      temperature: 0.3

    opportunity-scorer:
      model: "google/gemini-3.0-pro"
      max_tokens: 1500
      temperature: 0.2

    portfolio-advisor:
      model: "openai/gpt-5.2"
      escalation:
        - score_threshold: 70
          model: "anthropic/claude-sonnet-4.5"
        - score_threshold: 85
          model: "anthropic/claude-opus-4.5"
      max_tokens: 1500
      temperature: 0.1

    report-generator:
      model: "google/gemini-3.0-flash"
      max_tokens: 1000
      temperature: 0.5

    learning:
      model: "anthropic/claude-sonnet-4.5"
      max_tokens: 4000
      temperature: 0.7

    janitor:
      model: "google/gemini-3.0-pro"
      max_tokens: 2000
      temperature: 0.2

  # Fallback chain ordered by cost (cheapest first)
  # to minimize cost spikes during outages
  fallback_chain:
    - "google/gemini-3.0-flash"   # $0.10/$0.40
    - "google/gemini-3.0-pro"     # $1.25/$5.00
    - "openai/gpt-5.2"            # $1.75/$14.00
    - "anthropic/claude-sonnet-4.5" # $3.00/$15.00

  # Retry policy before falling back to next model
  retry:
    max_retries: 2
    initial_delay_ms: 500
    max_delay_ms: 5000
    exponential_backoff: true
    # Errors that trigger retry (vs immediate fallback)
    retryable_errors:
      - "rate_limit"
      - "service_unavailable"
      - "timeout"

  budget:
    monthly_limit_usd: 3000
    alert_threshold_pct: 80
    # Explicit degradation tiers when approaching/exceeding budget
    degradation_tiers:
      - threshold_pct: 80
        action: "alert"
        description: "Send warning notification"
      - threshold_pct: 90
        action: "reduce_premium"
        description: "Disable Opus escalation, cap at Sonnet"
      - threshold_pct: 95
        action: "reduce_frequency"
        description: "Reduce signal frequency from 1-min to 5-min"
      - threshold_pct: 100
        action: "emergency_mode"
        description: "Flash-only mode, 15-min frequency, critical alerts only"
```

## Cost Tracking

### Metrics

```python
# Prometheus metrics
model_tokens_total{agent, model, direction}  # input/output
model_cost_usd_total{agent, model}
model_requests_total{agent, model, status}   # success/failure/fallback
model_retry_total{agent, model}              # retry attempts before success/fallback
budget_usage_pct                             # current month budget utilization
degradation_tier_active{tier}                # which degradation tier is active
```

### Cost Dashboard

```python
# Daily cost by agent and model
SELECT
    date_trunc('day', timestamp) as day,
    agent_type,
    model_id,
    SUM(input_tokens * input_price + output_tokens * output_price) as cost_usd
FROM model_usage
GROUP BY 1, 2, 3
ORDER BY 1 DESC, cost_usd DESC;

# Hourly cost tracking for real-time budget monitoring
SELECT
    date_trunc('hour', timestamp) as hour,
    SUM(input_tokens * input_price + output_tokens * output_price) as cost_usd,
    SUM(SUM(input_tokens * input_price + output_tokens * output_price))
        OVER (ORDER BY date_trunc('hour', timestamp)) as cumulative_cost_usd
FROM model_usage
WHERE timestamp >= date_trunc('month', NOW())
GROUP BY 1
ORDER BY 1;
```

### Budget Enforcement

```python
@dataclass
class DegradationTier:
    threshold_pct: int
    action: str
    description: str

class BudgetEnforcer:
    def __init__(self, config: dict):
        self.limit = config["monthly_limit_usd"]
        self.tiers = [
            DegradationTier(**t) for t in config["degradation_tiers"]
        ]
        self.current_tier: Optional[DegradationTier] = None

    async def check_and_enforce(self) -> Optional[DegradationTier]:
        """
        Check budget and apply degradation tier if needed.

        Returns the newly activated tier, or None if no change.
        """
        current_cost = await get_monthly_cost()
        usage_pct = (current_cost / self.limit) * 100

        # Find the highest applicable tier
        applicable_tier = None
        for tier in sorted(self.tiers, key=lambda t: t.threshold_pct, reverse=True):
            if usage_pct >= tier.threshold_pct:
                applicable_tier = tier
                break

        # Apply tier if changed
        if applicable_tier != self.current_tier:
            old_tier = self.current_tier
            self.current_tier = applicable_tier

            if applicable_tier:
                await self._apply_degradation(applicable_tier)
                await send_alert(
                    f"Budget degradation: {applicable_tier.action}",
                    severity="critical" if applicable_tier.threshold_pct >= 95 else "warning",
                    details={
                        "usage_pct": usage_pct,
                        "tier": applicable_tier.action,
                        "description": applicable_tier.description
                    }
                )

            return applicable_tier

        return None

    async def _apply_degradation(self, tier: DegradationTier):
        """Apply the degradation action."""
        if tier.action == "alert":
            # Just alert, no operational changes
            pass
        elif tier.action == "reduce_premium":
            # Disable Opus, cap escalation at Sonnet
            await config_service.set("portfolio_advisor.max_model", "anthropic/claude-sonnet-4.5")
        elif tier.action == "reduce_frequency":
            # Increase signal interval to reduce API calls
            await config_service.set("signal_frequency_minutes", 5)
        elif tier.action == "emergency_mode":
            # Maximum cost reduction
            await config_service.set("signal_frequency_minutes", 15)
            await config_service.set("default_model", "google/gemini-3.0-flash")
            await config_service.set("escalation_enabled", False)
```

### Budget Alerts

```python
async def check_budget():
    """Legacy check_budget - use BudgetEnforcer for full enforcement."""
    current_month_cost = await get_monthly_cost()
    limit = config.budget.monthly_limit_usd
    threshold = config.budget.alert_threshold_pct / 100

    if current_month_cost >= limit:
        await trigger_hard_limit_action()
        await send_alert("Budget limit reached", severity="critical")
    elif current_month_cost >= limit * threshold:
        await send_alert(
            f"Budget at {current_month_cost/limit*100:.0f}%",
            severity="warning"
        )
```

## Acceptance Criteria

- [ ] Each agent uses model tier appropriate to task complexity
- [ ] Escalation to premium models for high-opportunity signals works
- [ ] Cost tracking dashboard shows spend by agent and model
- [ ] Monthly cost within budget
- [ ] Fallback chain works when primary model fails
- [ ] Retry logic exhausted before falling back to next model
- [ ] Fallback chain ordered cheapest-first to minimize outage costs
- [ ] Budget alerts fire at 80% and 100%
- [ ] Degradation tiers activate automatically at 80%, 90%, 95%, 100%
- [ ] Emergency mode restricts to Flash-only at 100% budget

## Implementation Notes

### OpenRouter Integration

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"]
)

async def call_model(model_id: str, messages: list, tools: list) -> Response:
    response = await client.chat.completions.create(
        model=model_id,
        messages=messages,
        tools=tools,
        extra_headers={
            "HTTP-Referer": "https://tradestream.io",
            "X-Title": "TradeStream Agent"
        }
    )
    return response
```

### Usage Logging

```python
async def log_usage(
    agent_type: str,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    success: bool,
    retries: int = 0,
    fallback_used: bool = False
):
    """Log model usage for cost tracking."""
    await db.execute(
        """
        INSERT INTO model_usage
        (agent_type, model_id, input_tokens, output_tokens, success, retries, fallback_used, timestamp)
        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
        """,
        agent_type, model_id, input_tokens, output_tokens, success, retries, fallback_used
    )

    # Update Prometheus metrics
    metrics.model_tokens_total.labels(
        agent=agent_type, model=model_id, direction="input"
    ).inc(input_tokens)
    metrics.model_tokens_total.labels(
        agent=agent_type, model=model_id, direction="output"
    ).inc(output_tokens)
    if retries > 0:
        metrics.model_retry_total.labels(
            agent=agent_type, model=model_id
        ).inc(retries)
```
