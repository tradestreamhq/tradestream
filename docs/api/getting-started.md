# TradeStream API — Getting Started

## Overview

The TradeStream API provides programmatic access to AI-powered trading signals,
strategy management, backtesting, and portfolio tracking. This guide walks you
through authentication, your first signal subscription, and webhook setup.

## Base URL

| Environment | URL                                  |
| ----------- | ------------------------------------ |
| Production  | `https://api.tradestream.io`         |
| Staging     | `https://staging-api.tradestream.io` |
| Local dev   | `http://localhost:8080`              |

## Authentication

TradeStream supports two authentication methods:

### 1. API Key (recommended for server-to-server)

Create an API key from the dashboard or via the API:

```bash
curl -X POST https://api.tradestream.io/api/v1/api-keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Trading Bot",
    "scopes": ["signals:read", "portfolio:read"],
    "expires_in_days": 90
  }'
```

Response (the full key is shown **only once**):

```json
{
  "key": "ts_live_sk_abc123def456ghi789jkl012mno345pqr678",
  "api_key": {
    "id": "key_abc123",
    "name": "My Trading Bot",
    "prefix": "ts_live_",
    "scopes": ["signals:read", "portfolio:read"]
  }
}
```

Use the key in the `X-API-Key` header:

```bash
curl https://api.tradestream.io/api/v1/signals \
  -H "X-API-Key: ts_live_sk_abc123..."
```

### 2. JWT Bearer Token (recommended for browser/mobile)

```bash
# Login
curl -X POST https://api.tradestream.io/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "your_password"}'
```

Response:

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "rt_abc123...",
  "token_type": "Bearer",
  "expires_in": 900
}
```

Use the access token:

```bash
curl https://api.tradestream.io/api/v1/signals \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..."
```

Refresh before it expires (15 min TTL):

```bash
curl -X POST https://api.tradestream.io/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "rt_abc123..."}'
```

### API Key Scopes

| Scope                 | Description                        |
| --------------------- | ---------------------------------- |
| `signals:read`        | Read signals and subscriptions     |
| `signals:write`       | Create/update signal subscriptions |
| `strategies:read`     | Read strategy specs and impls      |
| `strategies:write`    | Create/update strategies           |
| `portfolio:read`      | Read portfolio and positions       |
| `backtests:run`       | Submit backtest jobs               |
| `marketplace:read`    | Browse marketplace listings        |
| `marketplace:publish` | Publish strategies to marketplace  |

## Quick Start: Subscribe to Signals

### Step 1: Browse available strategies

```bash
curl https://api.tradestream.io/api/v1/marketplace/listings?sort_by=rating \
  -H "X-API-Key: YOUR_KEY"
```

### Step 2: Subscribe to a strategy's signals

```bash
curl -X POST https://api.tradestream.io/api/v1/signals/subscriptions \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": "strat_xyz789",
    "delivery_channels": ["webhook"],
    "webhook_url": "https://your-app.com/webhook/signals",
    "filters": {
      "min_strength": 0.7,
      "instruments": ["BTC/USD", "ETH/USD"],
      "timeframes": ["4h", "1d"]
    }
  }'
```

### Step 3: Verify your webhook

```bash
curl -X POST https://api.tradestream.io/api/v1/signals/subscriptions/SUB_ID/test \
  -H "X-API-Key: YOUR_KEY"
```

### Step 4: View incoming signals

```bash
curl "https://api.tradestream.io/api/v1/signals?status=active&limit=10" \
  -H "X-API-Key: YOUR_KEY"
```

## Webhook Setup

### Register a webhook endpoint

```bash
curl -X POST https://api.tradestream.io/api/v1/webhooks \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Signal Handler",
    "url": "https://your-app.com/webhooks/tradestream",
    "events": ["signal.created", "opportunity.created"]
  }'
```

### Verify webhook signatures

Every webhook delivery includes an `X-TradeStream-Signature` header with an
HMAC-SHA256 signature. Verify it in your handler:

```python
import hmac
import hashlib

def verify_signature(payload_bytes, signature, secret):
    expected = hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

### Webhook payload format

```json
{
  "event": "signal.created",
  "timestamp": "2026-03-19T10:30:00Z",
  "data": {
    "signal_id": "sig_abc123",
    "instrument": "BTC/USD",
    "direction": "BUY",
    "strength": 0.85,
    "entry_price": 67500.0,
    "stop_loss": 66000.0,
    "take_profit": 70000.0,
    "timeframe": "4h",
    "strategy_id": "strat_xyz789"
  }
}
```

### Webhook events

| Event                  | Description                           |
| ---------------------- | ------------------------------------- |
| `signal.created`       | New trading signal generated          |
| `signal.expired`       | Signal has expired                    |
| `opportunity.created`  | New high-score opportunity identified |
| `backtest.completed`   | Backtest job finished                 |
| `subscription.changed` | Billing subscription status changed   |

## Rate Limits

| Plan       | Requests/min | Requests/day |
| ---------- | -----------: | -----------: |
| Free       |           30 |        1,000 |
| Starter    |          120 |       10,000 |
| Pro        |          600 |       50,000 |
| Enterprise |        3,000 |    unlimited |

Rate limit headers in every response:

- `X-RateLimit-Limit` — max requests per window
- `X-RateLimit-Remaining` — requests left
- `X-RateLimit-Reset` — UTC epoch when window resets

HTTP 429 response when exceeded, with `Retry-After` header.

## Pagination

All list endpoints support `limit` and `offset` parameters:

```bash
curl "https://api.tradestream.io/api/v1/signals?limit=50&offset=100" \
  -H "X-API-Key: YOUR_KEY"
```

Response includes metadata:

```json
{
  "data": [...],
  "meta": {
    "total": 542,
    "limit": 50,
    "offset": 100
  }
}
```

## Error Handling

All errors return a consistent JSON structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid instrument symbol",
    "details": [{ "field": "instrument", "message": "Unknown symbol: INVALID" }]
  }
}
```

| HTTP Code | Error Code         | Description                    |
| --------- | ------------------ | ------------------------------ |
| 400       | `VALIDATION_ERROR` | Invalid request parameters     |
| 401       | `UNAUTHORIZED`     | Missing/invalid authentication |
| 403       | `FORBIDDEN`        | Insufficient scopes            |
| 404       | `NOT_FOUND`        | Resource not found             |
| 409       | `CONFLICT`         | Resource already exists        |
| 429       | `RATE_LIMITED`     | Too many requests              |
| 500       | `INTERNAL_ERROR`   | Server error                   |

## Interactive API Explorer

- **Swagger UI**: `https://api.tradestream.io/api/docs`
- **ReDoc**: `https://api.tradestream.io/api/redoc`
- **OpenAPI JSON**: `https://api.tradestream.io/api/openapi.json`
