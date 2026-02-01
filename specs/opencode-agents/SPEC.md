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
    0.25 * confidence +
    0.30 * normalize(expected_return) +
    0.20 * consensus_pct +
    0.15 * normalize(volatility) +
    0.10 * freshness
) * 100

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

## Metrics

- `agent_pipeline_duration_ms` - End-to-end pipeline latency
- `agent_processing_duration_ms` - Per-agent processing time
- `agent_failures_total` - Failed agent invocations
- `agent_messages_processed_total` - Messages by agent and channel
- `agent_model_tokens_total` - Token usage by agent and model
