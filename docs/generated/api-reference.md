# API Reference

Auto-generated from FastAPI service definitions.

**4 API services detected.**

## Learning Api

**Source:** `services/learning_api/app.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/learning/decisions` | list_decisions |
| `POST` | `/api/v1/learning/decisions` | create_decision |
| `GET` | `/api/v1/learning/decisions/{decision_id}` | get_decision |
| `PUT` | `/api/v1/learning/decisions/{decision_id}/outcome` | record_outcome |
| `GET` | `/api/v1/learning/patterns` | Detect performance patterns from recent decisions. |
| `GET` | `/api/v1/learning/performance` | Get aggregate performance metrics. |
| `POST` | `/api/v1/learning/similar` | Find similar historical situations based on market context. |

### `GET /api/v1/learning/decisions`

**Handler:** `list_decisions`

### `POST /api/v1/learning/decisions`

**Handler:** `create_decision`

### `GET /api/v1/learning/decisions/{decision_id}`

**Handler:** `get_decision`

### `PUT /api/v1/learning/decisions/{decision_id}/outcome`

**Handler:** `record_outcome`

### `GET /api/v1/learning/patterns`

**Handler:** `get_patterns`

Detect performance patterns from recent decisions.

### `GET /api/v1/learning/performance`

**Handler:** `get_performance`

Get aggregate performance metrics.

### `POST /api/v1/learning/similar`

**Handler:** `find_similar`

Find similar historical situations based on market context.

---

## Market Data Api

**Source:** `services/market_data_api/app.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/market/instruments` | List available instruments. |
| `GET` | `/api/v1/market/instruments/{symbol}/candles` | Get OHLCV candles for an instrument. |
| `GET` | `/api/v1/market/instruments/{symbol}/price` | Get current price for an instrument. |
| `GET` | `/api/v1/market/instruments/{symbol}/orderbook` | Get order book for an instrument. |

### `GET /api/v1/market/instruments`

**Handler:** `list_instruments`

List available instruments.

### `GET /api/v1/market/instruments/{symbol}/candles`

**Handler:** `get_candles`

Get OHLCV candles for an instrument.

### `GET /api/v1/market/instruments/{symbol}/price`

**Handler:** `get_price`

Get current price for an instrument.

### `GET /api/v1/market/instruments/{symbol}/orderbook`

**Handler:** `get_orderbook`

Get order book for an instrument.

Note: Order book data is currently a placeholder.
Full order book support requires a live exchange connection.

---

## Portfolio Api

**Source:** `services/portfolio_api/app.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/portfolio/state` | Get current portfolio state with all positions and aggregate metrics. |
| `GET` | `/api/v1/portfolio/positions` | List all open positions. |
| `GET` | `/api/v1/portfolio/positions/{instrument}` | Get position for a specific instrument. |
| `GET` | `/api/v1/portfolio/balance` | Get account balance (total realized + unrealized P&L). |
| `GET` | `/api/v1/portfolio/risk` | Get risk metrics across all positions. |
| `POST` | `/api/v1/portfolio/validate` | Validate a proposed trade against risk limits. |

### `GET /api/v1/portfolio/state`

**Handler:** `get_state`

Get current portfolio state with all positions and aggregate metrics.

### `GET /api/v1/portfolio/positions`

**Handler:** `list_positions`

List all open positions.

### `GET /api/v1/portfolio/positions/{instrument}`

**Handler:** `get_position`

Get position for a specific instrument.

### `GET /api/v1/portfolio/balance`

**Handler:** `get_balance`

Get account balance (total realized + unrealized P&L).

### `GET /api/v1/portfolio/risk`

**Handler:** `get_risk`

Get risk metrics across all positions.

### `POST /api/v1/portfolio/validate`

**Handler:** `validate_trade`

Validate a proposed trade against risk limits.

---

## Strategy Api

**Source:** `services/strategy_api/app.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/strategies/specs` | list_specs |
| `POST` | `/api/v1/strategies/specs` | create_spec |
| `GET` | `/api/v1/strategies/specs/{spec_id}` | get_spec |
| `PUT` | `/api/v1/strategies/specs/{spec_id}` | update_spec |
| `DELETE` | `/api/v1/strategies/specs/{spec_id}` | delete_spec |
| `GET` | `/api/v1/strategies/specs/{spec_id}/implementations` | list_spec_implementations |
| `POST` | `/api/v1/strategies/specs/{spec_id}/implementations` | create_implementation |
| `GET` | `/api/v1/strategies/implementations` | list_implementations |
| `GET` | `/api/v1/strategies/implementations/{impl_id}` | get_implementation |
| `DELETE` | `/api/v1/strategies/implementations/{impl_id}` | deactivate_implementation |
| `POST` | `/api/v1/strategies/implementations/{impl_id}/evaluate` | evaluate_implementation |
| `GET` | `/api/v1/strategies/implementations/{impl_id}/signal` | get_signal |

### `GET /api/v1/strategies/specs`

**Handler:** `list_specs`

### `POST /api/v1/strategies/specs`

**Handler:** `create_spec`

### `GET /api/v1/strategies/specs/{spec_id}`

**Handler:** `get_spec`

### `PUT /api/v1/strategies/specs/{spec_id}`

**Handler:** `update_spec`

### `DELETE /api/v1/strategies/specs/{spec_id}`

**Handler:** `delete_spec`

### `GET /api/v1/strategies/specs/{spec_id}/implementations`

**Handler:** `list_spec_implementations`

### `POST /api/v1/strategies/specs/{spec_id}/implementations`

**Handler:** `create_implementation`

### `GET /api/v1/strategies/implementations`

**Handler:** `list_implementations`

### `GET /api/v1/strategies/implementations/{impl_id}`

**Handler:** `get_implementation`

### `DELETE /api/v1/strategies/implementations/{impl_id}`

**Handler:** `deactivate_implementation`

### `POST /api/v1/strategies/implementations/{impl_id}/evaluate`

**Handler:** `evaluate_implementation`

### `GET /api/v1/strategies/implementations/{impl_id}/signal`

**Handler:** `get_signal`

---
