# Gateway API Specification

## Goal

Unified FastAPI backend service that consolidates all API endpoints including authentication, signal streaming, user settings, provider management, social features, and leaderboards.

## Target Behavior

The gateway-api is the single entry point for all frontend requests. It handles authentication, routes to appropriate handlers, and streams real-time signals via SSE.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      GATEWAY API (FastAPI)                       │
│                     Port 8000, Deployment                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Routers   │  │  Services   │  │      Middleware         │  │
│  ├─────────────┤  ├─────────────┤  ├─────────────────────────┤  │
│  │ /auth/*     │  │ auth_service│  │ CORS                    │  │
│  │ /api/signals│  │ email_svc   │  │ Rate Limiting           │  │
│  │ /api/user/* │  │ oauth_svc   │  │ Request Logging         │  │
│  │ /api/providers│ │ redis_pubsub│  │ Error Handling          │  │
│  │ /api/social │  │ db          │  │ Auth (JWT validation)   │  │
│  │ /api/leaders│  │ provider_stats│ │                         │  │
│  │ /api/achievements│           │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│                                                                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
   ┌───────────┐     ┌───────────┐     ┌───────────┐
   │ PostgreSQL│     │   Redis   │     │  Kafka    │
   │ (existing)│     │  pub/sub  │     │ (signals) │
   └───────────┘     └───────────┘     └───────────┘
```

## API Overview

### Endpoint Groups

| Prefix | Purpose | Auth |
|--------|---------|------|
| `/auth/*` | Authentication flows | None/Required |
| `/api/signals/*` | Signal streaming and history | Optional (demo allowed) |
| `/api/user/*` | User settings and preferences | Required |
| `/api/providers/*` | Provider profiles and stats | Optional |
| `/api/social/*` | Follows, reactions, comments | Required |
| `/api/leaderboards/*` | Rankings and leaderboards | Optional |
| `/api/achievements/*` | Streaks, badges, achievements | Required |
| `/api/referrals/*` | Referral program | Required |
| `/health` | Health check | None |

## Multi-Asset Signal System

### Supported Asset Types

| Asset Type | Asset Category | Symbol Format | Example |
|------------|---------------|---------------|---------|
| `crypto` | `crypto` | `{SYMBOL}` | `BTC`, `ETH`, `SOL` |
| `stock` | `equities` | `{TICKER}` | `AAPL`, `NVDA`, `TSLA` |
| `option` | `equities` | `{UNDERLYING} {STRIKE}{C/P} {EXPIRY}` | `AAPL 195C 3/15` |
| `etf` | `equities` | `{TICKER}` | `QQQ`, `SPY`, `ARKK` |
| `forex` | `forex` | `{BASE}/{QUOTE}` | `EUR/USD`, `GBP/USD` |
| `prediction` | `prediction` | Platform-specific | `Fed Rate Cut March` |

### Asset Categories (for filtering/display)

Categories consolidate asset types for simpler filtering:

| Category | Asset Types | Color |
|----------|-------------|-------|
| `crypto` | crypto | Orange |
| `equities` | stock, option, etf | Purple |
| `forex` | forex | Blue |
| `prediction` | prediction | Pink |

### GET /api/assets

List supported asset classes and their metadata.

**Response:**
```json
{
  "asset_types": [
    {"type": "crypto", "category": "crypto", "label": "Crypto", "enabled": true},
    {"type": "stock", "category": "equities", "label": "Stocks", "enabled": true},
    {"type": "option", "category": "equities", "label": "Options", "enabled": true},
    {"type": "etf", "category": "equities", "label": "ETFs", "enabled": true},
    {"type": "forex", "category": "forex", "label": "Forex", "enabled": true},
    {"type": "prediction", "category": "prediction", "label": "Predictions", "enabled": true}
  ],
  "categories": [
    {"id": "crypto", "label": "Crypto", "color": "#f97316"},
    {"id": "equities", "label": "Equities", "color": "#a855f7"},
    {"id": "forex", "label": "Forex", "color": "#3b82f6"},
    {"id": "prediction", "label": "Predictions", "color": "#ec4899"}
  ]
}
```

## Signals API

### GET /api/signals/stream (SSE)

Real-time signal stream via Server-Sent Events.

**Headers:**
```
Accept: text/event-stream
Authorization: Bearer <token>  (optional)
```

**Query Parameters (Server-side filtering):**
- `categories` (string, optional) - Comma-separated: `crypto,equities,forex,prediction`
- `asset_types` (string, optional) - Comma-separated: `crypto,stock,option,etf,forex,prediction`
- `min_score` (int, optional) - Minimum score 0-100
- `provider_ids` (string, optional) - Comma-separated provider UUIDs

**Response Stream:**
```
event: session_start
id: sess-123:1
data: {"session_id":"sess-123","timestamp":"2025-02-01T12:34:00Z","filters":{"categories":["crypto","equities"]}}

event: signal
id: sess-123:2
data: {"id":"abc123","asset_type":"crypto","asset_category":"crypto","symbol":"BTC","price":67420,"action":"buy","score":87,...}

event: signal
id: sess-123:3
data: {"id":"def456","asset_type":"option","asset_category":"equities","symbol":"AAPL 195C 3/15","action":"buy","score":84,"asset_data":{...}}

event: heartbeat
id: sess-123:4
data: {"timestamp":"2025-02-01T12:34:30Z","connected_providers":42}

event: error
data: {"code":"RATE_LIMITED","retry_after":30}
```

**Implementation:**

```python
from fastapi import APIRouter, Request, Depends
from sse_starlette.sse import EventSourceResponse
from ..services.redis_pubsub import subscribe_signals
from ..middleware.auth_middleware import get_current_user_or_demo

router = APIRouter(prefix="/api/signals", tags=["signals"])

@router.get("/stream")
async def signal_stream(
    request: Request,
    user=Depends(get_current_user_or_demo),
):
    """Stream real-time trading signals via SSE."""
    session_id = f"sess-{secrets.token_hex(8)}"
    sequence = 0

    async def event_generator():
        nonlocal sequence

        # Send session start
        sequence += 1
        yield {
            "event": "session_start",
            "id": f"{session_id}:{sequence}",
            "data": json.dumps({
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }),
        }

        # Subscribe to Redis channel
        async for signal in subscribe_signals("scored-signals"):
            if await request.is_disconnected():
                break

            sequence += 1
            yield {
                "event": "signal",
                "id": f"{session_id}:{sequence}",
                "data": signal.json(),
            }

    return EventSourceResponse(event_generator())
```

### GET /api/signals

Paginated signal history.

**Query Parameters:**
- `limit` (int, default=50, max=100) - Number of signals
- `offset` (int, default=0) - Pagination offset
- `symbol` (string, optional) - Filter by symbol
- `action` (string, optional) - Filter by buy/sell/hold/yes/no
- `min_score` (int, optional) - Minimum score 0-100
- `provider_id` (uuid, optional) - Filter by provider
- `categories` (string, optional) - Comma-separated asset categories
- `asset_types` (string, optional) - Comma-separated asset types

**Response:**
```json
{
  "signals": [
    {
      "id": "abc123",
      "asset_type": "crypto",
      "asset_category": "crypto",
      "symbol": "BTC",
      "action": "buy",
      "score": 87,
      "reasoning": "RSI oversold bounce with MACD turning positive. 4/5 strategies agree.",
      "provider": {
        "id": "...",
        "name": "CryptoKing_42",
        "avatar_url": "...",
        "win_rate": 67,
        "followers": 12400,
        "verified": true
      },
      "asset_data": {
        "price": 67420.00,
        "price_change_24h": 0.032
      },
      "reactions": {
        "like": 42,
        "fire": 15,
        "rocket": 8
      },
      "comment_count": 12,
      "created_at": "2026-02-15T12:34:56Z"
    },
    {
      "id": "def456",
      "asset_type": "option",
      "asset_category": "equities",
      "symbol": "AAPL 195C 3/15",
      "action": "buy",
      "score": 84,
      "reasoning": "Unusual call volume. IV crush opportunity post-earnings.",
      "provider": {
        "id": "...",
        "name": "OptionsFlow",
        "avatar_url": "...",
        "win_rate": 71,
        "followers": 9200,
        "verified": true
      },
      "asset_data": {
        "underlying": "AAPL",
        "strike": 195.00,
        "option_type": "call",
        "expiry": "2026-03-15",
        "premium": 4.20,
        "greeks": {
          "delta": 0.45,
          "theta": -0.08,
          "gamma": 0.03,
          "vega": 0.22,
          "iv": 0.32
        },
        "open_interest": 12500,
        "volume": 3400
      },
      "reactions": {...},
      "comment_count": 5,
      "created_at": "2026-02-15T12:30:00Z"
    },
    {
      "id": "ghi789",
      "asset_type": "prediction",
      "asset_category": "prediction",
      "symbol": "Fed Rate Cut March",
      "action": "yes",
      "score": 79,
      "reasoning": "Probability RSI oversold at 32. Market underpricing based on Fed commentary.",
      "provider": {
        "id": "...",
        "name": "MacroOracle",
        "avatar_url": "...",
        "win_rate": 71,
        "followers": 8900,
        "verified": true
      },
      "asset_data": {
        "platform": "polymarket",
        "market_id": "...",
        "market_question": "Will the Fed cut rates in March 2026?",
        "probability": 0.68,
        "prob_change_24h": 0.05,
        "volume_usd": 2500000,
        "resolution_date": "2026-03-20"
      },
      "reactions": {...},
      "comment_count": 8,
      "created_at": "2026-02-15T12:25:00Z"
    }
  ],
  "total": 1234,
  "limit": 50,
  "offset": 0
}
```

### GET /api/signals/{signal_id}

Get detailed signal with full reasoning.

**Response:**
```json
{
  "signal_id": "abc123",
  "symbol": "ETH/USD",
  "action": "BUY",
  "confidence": 0.82,
  "opportunity_score": 87,
  "opportunity_tier": "HOT",
  "opportunity_factors": {
    "confidence": {"value": 0.82, "contribution": 20.5},
    "expected_return": {"value": 0.032, "contribution": 30.0},
    "consensus": {"value": 0.80, "contribution": 16.0},
    "volatility": {"value": 0.021, "contribution": 10.5},
    "freshness": {"value": 2, "contribution": 10.0}
  },
  "strategy_breakdown": [
    {"name": "RSI_REVERSAL", "signal": "BUY", "score": 0.89},
    {"name": "MACD_CROSS", "signal": "BUY", "score": 0.85},
    {"name": "BOLLINGER_BOUNCE", "signal": "BUY", "score": 0.78},
    {"name": "EMA_TREND", "signal": "BUY", "score": 0.72},
    {"name": "VOLUME_BREAKOUT", "signal": "SELL", "score": 0.65}
  ],
  "reasoning": "Strong consensus among top strategies. RSI shows oversold recovery at 28, MACD just crossed bullish with histogram expanding. Volume confirms breakout attempt.",
  "market_context": {
    "current_price": 2345.67,
    "price_change_1h": 0.023,
    "volume_ratio": 1.5,
    "volatility_1h": 0.021
  },
  "provider": {...},
  "reactions": {...},
  "comments": [...],
  "created_at": "2025-02-01T12:34:56Z"
}
```

## User API

### GET /api/user/settings

Get current user settings.

**Response:**
```json
{
  "risk_tolerance": "moderate",
  "min_opportunity_score": 0.60,
  "default_action_filter": ["BUY", "SELL", "HOLD"],
  "theme": "dark",
  "timezone": "America/New_York",
  "onboarding_completed": true,
  "onboarding_step": 5
}
```

### PUT /api/user/settings

Update user settings.

**Request:**
```json
{
  "risk_tolerance": "aggressive",
  "min_opportunity_score": 0.70,
  "theme": "dark"
}
```

### GET /api/user/watchlist

Get user's watchlist.

**Response:**
```json
{
  "watchlist": [
    {
      "symbol": "BTC/USD",
      "notes": "Long-term hold",
      "alert_enabled": true,
      "position_size": 0.5,
      "entry_price": 42000.00,
      "added_at": "2025-01-15T10:00:00Z"
    },
    {
      "symbol": "ETH/USD",
      "notes": null,
      "alert_enabled": true,
      "position_size": null,
      "entry_price": null,
      "added_at": "2025-01-20T14:30:00Z"
    }
  ]
}
```

### POST /api/user/watchlist

Add symbol to watchlist.

**Request:**
```json
{
  "symbol": "SOL/USD",
  "notes": "Watching for entry",
  "alert_enabled": true
}
```

### DELETE /api/user/watchlist/{symbol}

Remove symbol from watchlist.

### GET /api/user/saved-views

Get saved filter views.

### POST /api/user/saved-views

Create new saved view.

**Request:**
```json
{
  "name": "High Confidence BUY",
  "filters": {
    "actions": ["BUY"],
    "minOpportunityScore": 0.80
  }
}
```

## Providers API

### GET /api/providers

List providers with stats.

**Query Parameters:**
- `limit` (int, default=20)
- `offset` (int)
- `sort` (string) - `followers`, `win_rate`, `return`, `streak`
- `verified_only` (bool, default=false)

**Response:**
```json
{
  "providers": [
    {
      "user_id": "...",
      "display_name": "CryptoKing_42",
      "bio": "Trading since 2017. Focus on momentum strategies.",
      "avatar_url": "...",
      "risk_level": "aggressive",
      "specialties": ["crypto", "momentum"],
      "total_signals": 1247,
      "win_rate": 0.6734,
      "avg_return": 0.0423,
      "total_return": 2.45,
      "current_streak": 14,
      "longest_streak": 28,
      "follower_count": 12400,
      "is_verified": true,
      "verification_level": "pro"
    }
  ],
  "total": 456,
  "limit": 20,
  "offset": 0
}
```

### GET /api/providers/{provider_id}

Get provider profile with recent signals.

**Response:**
```json
{
  "user_id": "...",
  "display_name": "CryptoKing_42",
  "bio": "Trading since 2017...",
  "strategy_description": "I focus on RSI reversals and MACD crossovers...",
  "avatar_url": "...",
  "banner_url": "...",
  "website_url": "https://...",
  "twitter_handle": "cryptoking42",
  "risk_level": "aggressive",
  "specialties": ["crypto", "momentum"],
  "stats": {
    "total_signals": 1247,
    "win_count": 840,
    "loss_count": 407,
    "win_rate": 0.6734,
    "avg_return": 0.0423,
    "total_return": 2.45,
    "sharpe_ratio": 1.82,
    "max_drawdown": 0.15,
    "current_streak": 14,
    "longest_streak": 28,
    "follower_count": 12400,
    "signal_likes_total": 45600
  },
  "is_verified": true,
  "verification_level": "pro",
  "verified_at": "2024-06-15T00:00:00Z",
  "recent_signals": [...],
  "is_following": false,  // For authenticated user
  "created_at": "2023-01-01T00:00:00Z"
}
```

### GET /api/providers/{provider_id}/signals

Get provider's signal history.

### POST /api/providers/become

Apply to become a provider.

**Request:**
```json
{
  "display_name": "MyTradingName",
  "bio": "Experienced trader...",
  "strategy_description": "I specialize in...",
  "risk_level": "moderate"
}
```

## Social API

### POST /api/social/follow/{provider_id}

Follow a provider.

**Request:**
```json
{
  "notify_on_signal": true
}
```

**Response:**
```json
{
  "following": true,
  "provider_id": "...",
  "notify_on_signal": true,
  "followed_at": "2025-02-01T12:34:56Z"
}
```

### DELETE /api/social/follow/{provider_id}

Unfollow a provider.

### GET /api/social/following

Get list of followed providers.

**Response:**
```json
{
  "following": [
    {
      "provider": {
        "user_id": "...",
        "display_name": "CryptoKing_42",
        "avatar_url": "...",
        "win_rate": 0.67,
        "follower_count": 12400
      },
      "notify_on_signal": true,
      "followed_at": "2025-01-15T10:00:00Z"
    }
  ],
  "total": 5
}
```

### GET /api/social/feed

Get social feed from followed providers.

**Response:**
```json
{
  "signals": [
    {
      "signal_id": "...",
      "provider": {...},
      "symbol": "ETH/USD",
      "action": "BUY",
      "opportunity_score": 87,
      "commentary": "Strong setup here...",
      "reactions": {"like": 42, "fire": 15},
      "comment_count": 12,
      "created_at": "2025-02-01T12:34:56Z"
    }
  ],
  "total": 50,
  "limit": 20,
  "offset": 0
}
```

### POST /api/social/signals/{signal_id}/react

Add reaction to signal.

**Request:**
```json
{
  "reaction_type": "fire"
}
```

### DELETE /api/social/signals/{signal_id}/react/{reaction_type}

Remove reaction from signal.

### GET /api/social/signals/{signal_id}/comments

Get comments for signal.

### POST /api/social/signals/{signal_id}/comments

Add comment to signal.

**Request:**
```json
{
  "content": "Great call! I'm in.",
  "parent_id": null
}
```

## Leaderboards API

### GET /api/leaderboards/{type}

Get leaderboard by type.

**Types:**
- `followers` - Most followed providers
- `win_rate` - Highest win rate (min 10 signals)
- `return` - Highest average return
- `streak` - Longest current streak
- `rising` - Fastest growing (follower rate)

**Query Parameters:**
- `limit` (int, default=50, max=100)
- `period` (string, optional) - `all`, `month`, `week`

**Response:**
```json
{
  "leaderboard": "followers",
  "period": "all",
  "entries": [
    {
      "rank": 1,
      "provider": {
        "user_id": "...",
        "display_name": "CryptoKing_42",
        "avatar_url": "...",
        "is_verified": true
      },
      "value": 12400,
      "change": 234,
      "change_period": "week"
    }
  ],
  "updated_at": "2025-02-01T12:00:00Z"
}
```

## Achievements API

### GET /api/achievements

Get all achievement definitions.

**Response:**
```json
{
  "achievements": [
    {
      "id": "first_win",
      "name": "First Win",
      "description": "Your first profitable signal",
      "category": "trading",
      "icon": "🏆",
      "points": 25,
      "rarity": "common"
    }
  ]
}
```

### GET /api/achievements/me

Get user's unlocked achievements and progress.

**Response:**
```json
{
  "unlocked": [
    {
      "achievement_id": "first_win",
      "unlocked_at": "2025-01-15T10:00:00Z"
    },
    {
      "achievement_id": "streak_7",
      "unlocked_at": "2025-01-22T00:00:00Z"
    }
  ],
  "total_points": 75,
  "next_achievements": [
    {
      "id": "win_10",
      "name": "Getting Started",
      "progress": 7,
      "target": 10
    }
  ]
}
```

### GET /api/achievements/streaks

Get user's current streaks.

**Response:**
```json
{
  "streaks": [
    {
      "streak_type": "login",
      "current_count": 14,
      "longest_count": 21,
      "last_activity_date": "2025-02-01"
    },
    {
      "streak_type": "profitable_signal",
      "current_count": 3,
      "longest_count": 8,
      "last_activity_date": "2025-02-01"
    }
  ]
}
```

## Referrals API

### GET /api/referrals

Get user's referral dashboard.

**Response:**
```json
{
  "referral_code": "KING42",
  "referral_url": "https://tradestream.io/join/KING42",
  "tier": {
    "id": "silver",
    "name": "Silver",
    "referrer_reward": 50.00,
    "referee_reward": 25.00
  },
  "stats": {
    "total_referrals": 7,
    "qualified_referrals": 5,
    "pending_referrals": 2,
    "total_earned": 250.00,
    "pending_earnings": 100.00
  },
  "next_tier": {
    "id": "gold",
    "name": "Gold",
    "referrals_needed": 3,
    "referrer_reward": 75.00
  },
  "referrals": [
    {
      "referee_name": "Trader***",
      "status": "qualified",
      "reward_amount": 50.00,
      "created_at": "2025-01-20T10:00:00Z",
      "qualified_at": "2025-01-21T14:30:00Z"
    }
  ]
}
```

### POST /api/referrals/custom-code

Set custom referral code (premium feature).

**Request:**
```json
{
  "code": "CRYPTOKING"
}
```

## File Structure

```
services/gateway/
├── main.py                    # FastAPI app entry point
├── config.py                  # Settings and configuration
├── routers/
│   ├── __init__.py
│   ├── auth.py               # /auth/* endpoints
│   ├── signals.py            # /api/signals/* endpoints
│   ├── users.py              # /api/user/* endpoints
│   ├── providers.py          # /api/providers/* endpoints
│   ├── social.py             # /api/social/* endpoints
│   ├── leaderboards.py       # /api/leaderboards/* endpoints
│   ├── achievements.py       # /api/achievements/* endpoints
│   ├── referrals.py          # /api/referrals/* endpoints
│   └── health.py             # /health endpoint
├── services/
│   ├── __init__.py
│   ├── auth_service.py       # JWT, password hashing
│   ├── email_service.py      # Resend integration
│   ├── oauth_service.py      # OAuth provider clients
│   ├── redis_pubsub.py       # Redis pub/sub for SSE
│   ├── provider_stats.py     # Calculate provider metrics
│   ├── achievement_service.py # Achievement/streak logic
│   └── db.py                 # Database connection pool
├── models/
│   ├── __init__.py
│   ├── auth.py               # Auth request/response models
│   ├── user.py               # User models
│   ├── signal.py             # Signal models
│   ├── provider.py           # Provider models
│   └── achievement.py        # Achievement models
├── middleware/
│   ├── __init__.py
│   ├── auth_middleware.py    # JWT validation
│   ├── rate_limiter.py       # Rate limiting
│   └── error_handler.py      # Global error handling
├── requirements.txt
├── Dockerfile
└── tests/
    ├── __init__.py
    ├── test_auth.py
    ├── test_signals.py
    ├── test_providers.py
    ├── test_social.py
    └── conftest.py           # Pytest fixtures
```

## main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .config import settings
from .routers import auth, signals, users, providers, social, leaderboards, achievements, referrals, health
from .middleware.error_handler import add_error_handlers
from .middleware.rate_limiter import RateLimitMiddleware
from .services.db import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title="TradeStream Gateway API",
    description="Unified API for the TradeStream trading signal platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.add_middleware(RateLimitMiddleware)

# Error handlers
add_error_handlers(app)

# Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(signals.router)
app.include_router(users.router)
app.include_router(providers.router)
app.include_router(social.router)
app.include_router(leaderboards.router)
app.include_router(achievements.router)
app.include_router(referrals.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## config.py

```python
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10

    # Redis
    REDIS_URL: str

    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    # OAuth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: str

    # Email
    RESEND_API_KEY: str

    # URLs
    API_URL: str = "https://api.tradestream.io"
    FRONTEND_URL: str = "https://tradestream.io"

    # CORS
    CORS_ORIGINS: List[str] = [
        "https://tradestream.io",
        "https://www.tradestream.io",
        "http://localhost:3000",
    ]

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    class Config:
        env_file = ".env"


settings = Settings()
```

## requirements.txt

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
asyncpg>=0.29.0
redis>=5.0.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
authlib>=1.3.0
httpx>=0.26.0
resend>=0.7.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
sse-starlette>=1.8.0
python-multipart>=0.0.6
```

## Dockerfile

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Redis Pub/Sub Integration

### Signal Publisher (strategy-consumer modification)

```python
# Add to services/strategy_consumer/main.py

import redis.asyncio as redis

async def publish_signal_to_redis(signal: Signal, redis_client: redis.Redis):
    """Publish new signal to Redis for SSE streaming."""
    await redis_client.publish(
        "scored-signals",
        signal.model_dump_json(),
    )
```

### Signal Subscriber (gateway-api)

```python
# services/gateway/services/redis_pubsub.py

import redis.asyncio as redis
from typing import AsyncGenerator
from ..config import settings
from ..models.signal import Signal


async def subscribe_signals(channel: str) -> AsyncGenerator[Signal, None]:
    """Subscribe to Redis channel and yield signals."""
    redis_client = await redis.from_url(settings.REDIS_URL)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                signal = Signal.model_validate_json(message["data"])
                yield signal
    finally:
        await pubsub.unsubscribe(channel)
        await redis_client.close()
```

## Rate Limiting

```python
# services/gateway/middleware/rate_limiter.py

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis
from ..config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.redis = None

    async def dispatch(self, request: Request, call_next):
        if self.redis is None:
            self.redis = await redis.from_url(settings.REDIS_URL)

        # Get client IP
        client_ip = request.client.host
        if "x-forwarded-for" in request.headers:
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()

        # Rate limit key
        key = f"rate_limit:{client_ip}:{request.url.path}"

        # Check rate limit
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, 60)  # 1 minute window

        # Get limit based on endpoint
        limit = self._get_limit(request.url.path)

        if current > limit:
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(await self.redis.ttl(key)),
                },
            )

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current))

        return response

    def _get_limit(self, path: str) -> int:
        """Get rate limit for path."""
        limits = {
            "/auth/register": 5,
            "/auth/login": 10,
            "/auth/forgot-password": 3,
            "/api/signals/stream": 10,
        }
        for prefix, limit in limits.items():
            if path.startswith(prefix):
                return limit
        return settings.RATE_LIMIT_PER_MINUTE
```

## Error Handling

```python
# services/gateway/middleware/error_handler.py

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


def add_error_handlers(app: FastAPI):
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )
```

## Constraints

- FastAPI with async throughout
- Connection pooling for PostgreSQL (asyncpg)
- Redis for pub/sub and caching
- JWT validation on all protected routes
- Rate limiting per IP address
- CORS configured for frontend domains
- Health check endpoint for K8s probes

## Acceptance Criteria

- [ ] Health endpoint returns 200 with status
- [ ] Auth endpoints work (see auth-service spec)
- [ ] Signal SSE stream delivers events in real-time
- [ ] Signal history endpoint returns paginated results
- [ ] User settings CRUD operations work
- [ ] Watchlist CRUD operations work
- [ ] Provider list with stats works
- [ ] Provider profile with signals works
- [ ] Follow/unfollow updates follower count
- [ ] Social feed returns followed providers' signals
- [ ] Reactions can be added/removed
- [ ] Comments can be posted
- [ ] Leaderboards return ranked providers
- [ ] Achievements list returned with progress
- [ ] Streaks tracked correctly
- [ ] Referral dashboard shows stats
- [ ] Rate limiting enforced per IP
- [ ] CORS allows configured origins
- [ ] Error responses follow consistent format
- [ ] All endpoints have proper auth checks

## Notes

### Demo Mode Access

Demo users (with `is_demo: true` JWT) can access:
- `/api/signals/stream` - Full signal stream
- `/api/signals` - Signal history
- `/api/providers` - Provider list
- `/api/providers/{id}` - Provider profile
- `/api/leaderboards/*` - All leaderboards

Demo users cannot access:
- `/api/user/*` - Settings, watchlist
- `/api/social/*` - Follow, react, comment
- `/api/achievements/*` - User achievements
- `/api/referrals/*` - Referral program

### Caching Strategy

- Provider stats: Redis, 5-minute TTL
- Leaderboards: PostgreSQL materialized view, hourly refresh
- Signal history: No cache (real-time)
- Achievement definitions: Redis, 1-hour TTL

### Performance Considerations

- Use `asyncpg` connection pool (10 connections default)
- SSE connections managed with background tasks
- Materialized views for leaderboard queries
- Pagination on all list endpoints
