# Viral Trading Signal Platform

## Goal

Transform TradeStream into the **TradingView of trading signals** - a social platform where users follow top signal providers, copy trades, share wins, and providers monetize their strategies earning $10K+/month.

## Vision

| Feature           | Why It Works                             | Example                         |
| ----------------- | ---------------------------------------- | ------------------------------- |
| Copy Trading      | Network effects - value grows with users | eToro's fastest-growing segment |
| Leaderboards      | Social proof drives FOMO                 | TradingView's Ideas Hub         |
| Win Sharing       | Free marketing, #RichTok culture         | Robinhood screenshot culture    |
| Streaks           | 47% higher retention                     | Duolingo, Snapchat              |
| Referrals         | Viral coefficient > 0.15                 | $50 referrer + $25 referee      |
| Provider Earnings | Creators attract audiences               | YouTube/Twitch model            |

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND (agent-dashboard)                   │
│  React + Vite + shadcn/ui (Deployment, port 3000)               │
│  Landing → Auth Flow → Dashboard (SSE signals, settings, chat)  │
└─────────────────────────────────────────────────────────────────┘
                              │ Ingress (tradestream.io)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      GATEWAY API (FastAPI)                       │
│  Deployment, port 8000, unified entry point                     │
│  /auth/* │ /api/signals (SSE) │ /api/user/* │ /api/providers   │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   ┌───────────┐        ┌───────────┐        ┌───────────┐
   │ PostgreSQL│        │   Redis   │        │ Kafka     │
   │ (existing)│        │ (existing)│        │ (existing)│
   │ +V6-V12   │        │ +pub/sub  │        │ signals   │
   └───────────┘        └───────────┘        └───────────┘
```

## Sub-Specifications

Implementation is divided into focused specs. Each spec is self-contained with its own acceptance criteria.

| Spec                                                 | Purpose                                                  | Priority |
| ---------------------------------------------------- | -------------------------------------------------------- | -------- |
| [database-migrations](./database-migrations/SPEC.md) | V6-V12 SQL migrations for users, providers, achievements | P0       |
| [auth-service](./auth-service/SPEC.md)               | Custom auth with OAuth, JWT, email verification          | P0       |
| [gateway-api](./gateway-api/SPEC.md)                 | Unified FastAPI backend consolidating all APIs           | P0       |
| [agent-dashboard](./agent-dashboard/SPEC.md)         | React frontend with landing, auth, dashboard             | P0       |
| [social-features](./social-features/SPEC.md)         | Provider profiles, follows, feed, reactions              | P1       |
| [gamification](./gamification/SPEC.md)               | Streaks, achievements, badges, referrals                 | P1       |
| [helm-deployment](./helm-deployment/SPEC.md)         | K8s templates for new services                           | P0       |

## Multi-Asset Roadmap

| Phase      | Assets             | Markets            | Timeline  |
| ---------- | ------------------ | ------------------ | --------- |
| **Launch** | Crypto             | BTC, ETH, top 20   | Now       |
| **Q2**     | Prediction Markets | Kalshi, Polymarket | +3 months |
| **Q3**     | Forex              | EUR/USD, majors    | +6 months |
| **Q4**     | Stocks             | S&P 500, NASDAQ    | +9 months |

## Key Technical Decisions

| Decision        | Choice                   | Rationale                                |
| --------------- | ------------------------ | ---------------------------------------- |
| OAuth providers | Google + GitHub          | Widest developer + consumer reach        |
| Email service   | Resend                   | 3000 free/month, API-based, K8s-friendly |
| Demo mode       | Full read access         | Same signals, no persistence             |
| Infrastructure  | K8s via Helm             | Consistent with existing setup           |
| Monetization    | Freemium + provider subs | Platform takes 20-30%                    |
| Frontend stack  | Vite + React + shadcn/ui | Modern DX, good defaults                 |
| Backend         | FastAPI (Python)         | Async, fast, matches existing services   |

## Implementation Order

### Phase 0: Foundation (Week 1-2)

1. Database migrations V6-V8 (users, settings, notifications)
2. Gateway API skeleton with health endpoint
3. Auth endpoints (register, login, OAuth)
4. Email verification via Resend
5. Signal SSE endpoint (Redis pub/sub)
6. Helm templates for gateway-api

### Phase 1: Frontend Foundation (Week 3-4)

7. Agent dashboard scaffold (Vite + React + TypeScript)
8. shadcn/ui component setup
9. Auth hooks and API client
10. Landing page with hero + CTAs
11. Login/Register pages with OAuth buttons
12. Protected routes

### Phase 2: Dashboard Core (Week 5-6)

13. Dashboard layout (header, sidebar, main)
14. SignalStream component (virtualized)
15. SignalCard with expand/collapse
16. useAgentStream SSE hook
17. FilterBar and Settings panel
18. Helm template for agent-dashboard

### Phase 3: Social Features (Week 7-9)

19. Database migrations V9 (providers, follows, reactions)
20. Provider profiles with stats
21. Follow/unfollow system
22. Social feed component
23. Leaderboards (multiple rankings)
24. Win card generation + sharing

### Phase 4: Gamification (Week 10-11)

25. Database migrations V10-V11 (achievements, referrals)
26. Streak tracking (login, profitable, posting)
27. Achievement/badge system
28. Referral program with tiers
29. Referral dashboard

### Phase 5: Polish & Launch (Week 12)

30. Onboarding flow
31. Push notifications
32. Telegram integration
33. Mobile responsive polish
34. Compliance disclaimers

## Existing Infrastructure (Available)

### Data Stores (Already Deployed via Helm)

| Component  | Version | Purpose                    | Status  |
| ---------- | ------- | -------------------------- | ------- |
| PostgreSQL | 17.6.0  | Strategies, signals, specs | RUNNING |
| Redis      | 8.2.1   | Cache, pub/sub             | RUNNING |
| InfluxDB   | 2.x     | Time-series candle data    | RUNNING |
| Kafka      | 3-node  | Message broker             | RUNNING |

### Existing Services

| Service                     | Type    | Purpose            | Status   |
| --------------------------- | ------- | ------------------ | -------- |
| strategy-monitor-api        | Flask   | Strategy queries   | DEPLOYED |
| strategy-monitor-ui         | Static  | Basic UI           | DEPLOYED |
| candle-ingestor             | CronJob | OHLCV data         | RUNNING  |
| strategy-consumer           | CronJob | Kafka → PostgreSQL | RUNNING  |
| strategy-discovery-pipeline | Flink   | GA optimization    | RUNNING  |

### Existing Database Schema (V1-V5 migrations)

- `Strategies` - GA-discovered strategies
- `strategy_specs` - Strategy definitions
- `strategy_implementations` - Parameter optimizations
- `strategy_performance` - Performance tracking
- `signals` - Trade signal history
- `walk_forward_results` - Validation metrics

## Success Metrics

### Acquisition (Viral Growth)

| Metric             | Target | How                        |
| ------------------ | ------ | -------------------------- |
| Viral coefficient  | > 0.15 | Referrals + social sharing |
| Organic/paid ratio | > 3:1  | Content, word of mouth     |
| Week 1 signups     | 1,000  | Launch campaign + demo     |

### Engagement (Retention)

| Metric        | Target | How                      |
| ------------- | ------ | ------------------------ |
| DAU/MAU       | > 20%  | Streaks, daily signals   |
| Sessions/week | > 5    | Real-time signal FOMO    |
| D1 retention  | > 40%  | Onboarding, first signal |
| D7 retention  | > 25%  | Streaks, achievements    |
| D30 retention | > 15%  | Social graph, following  |

### Product-Market Fit

| Metric                  | Target | How                  |
| ----------------------- | ------ | -------------------- |
| NPS                     | > 50   | Survey after 30 days |
| "Very disappointed"     | > 40%  | Sean Ellis test      |
| Weekly active providers | > 50   | Provider dashboard   |

## Competitive Differentiation

| Competitor       | What They Do             | Why We're Different                                     |
| ---------------- | ------------------------ | ------------------------------------------------------- |
| TradingView      | Charts + manual analysis | **Automated signals** from 40M+ GA-optimized strategies |
| Clawdbot         | AI trading bot           | **Strategy consensus**, not single AI opinion           |
| Signal groups    | Manual Telegram signals  | **Verified performance**, transparent stats             |
| eToro CopyTrader | Copy human traders       | **Copy AI-discovered strategies** with backtests        |

### The Moat

```
Data Flywheel:
More users → More signals followed → Better provider stats →
More providers → More strategies → Better signals → More users
```

## Acceptance Criteria (Platform-Level)

- [ ] User can sign up via email or OAuth (Google/GitHub)
- [ ] User can enter demo mode without signup
- [ ] Dashboard shows live signals via SSE
- [ ] User can follow signal providers
- [ ] Social feed shows followed providers' signals
- [ ] Leaderboards show top providers by multiple metrics
- [ ] Users can generate and share win cards
- [ ] Streak system tracks daily engagement
- [ ] Achievement badges unlock based on milestones
- [ ] Referral program tracks and rewards referrals
- [ ] All services deploy via Helm to K8s
- [ ] Mobile responsive on all pages

## Notes

### Demo Mode Strategy

- Anonymous JWT with `is_demo: true`
- Permissions: `["read:signals"]` only
- No persistence (settings reset on refresh)
- Full signal access (same data as authenticated users)
- Prominent "Sign up to save your settings" CTA

### Provider Economy (Q3+)

- Top providers earn 70-80% of subscription revenue
- Platform takes 20-30% fee
- Verification badges for consistent performance
- Monthly payout via Stripe Connect

### Prediction Markets (Q2)

- Kalshi and Polymarket API integration
- Custom probability indicators (ProbabilityRSI, TimeDecay)
- Signals for prediction market positions
- Separate leaderboard for prediction accuracy
