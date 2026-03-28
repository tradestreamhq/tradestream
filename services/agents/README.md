# Agent Framework (`services/agents/`)

Shared scaffolding for TradeStream LLM-driven agents. Provides an OpenRouter
client, an MCP routing client, and a base class that wires them together.

## Components

| Module | Purpose |
|---|---|
| `openrouter_client.py` | Chat completions via OpenRouter with per-call model override and exponential-backoff retries on 429/5xx |
| `mcp_client.py` | Routes MCP tool calls to `strategy-mcp`, `market-mcp`, and `signal-mcp` K8s services |
| `base.py` | Abstract `BaseAgent` with `run()` and `call_mcp_tool()` helpers |

## How to implement a new agent

1. **Create a new service directory** (e.g. `services/my_agent/`).

2. **Subclass `BaseAgent`** and implement `run()`:

```python
from services.agents.base import BaseAgent

class MyAgent(BaseAgent):
    def run(self, *, symbol: str) -> dict:
        # 1. Call MCP tools to gather data
        strategies = self.call_mcp_tool("strategy", "get_top_strategies", {"symbol": symbol})
        market = self.call_mcp_tool("market", "get_market_summary", {"symbol": symbol})

        # 2. Send data to the LLM
        response = self.openrouter.chat(
            messages=[
                {"role": "system", "content": "You are a trading analyst."},
                {"role": "user", "content": f"Analyze {symbol}: {strategies}, {market}"},
            ],
            model="anthropic/claude-haiku-4-5",  # optional per-call override
        )

        # 3. Return the result
        return {"analysis": response.choices[0].message.content}
```

3. **Wire it up in `main.py`**:

```python
from services.my_agent.agent import MyAgent

agent = MyAgent("my-agent")
result = agent.run(symbol="BTC-USD")
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | *(required)* | API key for OpenRouter |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Base URL override |
| `STRATEGY_MCP_URL` | `http://strategy-mcp:8080` | Strategy MCP service URL |
| `MARKET_MCP_URL` | `http://market-mcp:8080` | Market MCP service URL |
| `SIGNAL_MCP_URL` | `http://signal-mcp:8080` | Signal MCP service URL |

## Running tests

```bash
bazel test //services/agents/...
```
