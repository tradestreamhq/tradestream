# 8-Week Sprint Plan: Path to Revenue

**Created**: 2026-03-12
**Goal**: Ship the simplest version of TradeStream that generates recurring revenue

---

## Current State Assessment

### What's Production-Ready (Running 240+ Days)
- **Strategy Discovery Engine**: 40M+ strategy configurations discovered via genetic algorithms across 80+ crypto symbols
- **Market Data Pipeline**: 1,000+ candles/minute from Binance, Coinbase, and Kraken via CCXT
- **Strategy Storage**: PostgreSQL with full backtest metrics (Sharpe, drawdown, win rate, profit factor)
- **Walk-Forward Validation**: Out-of-sample testing pipeline for strategy quality assurance
- **Infrastructure**: Kubernetes cluster with Helm charts, Kafka, InfluxDB, PostgreSQL, Redis

### What's Code-Complete but Not Deployed
- Signal Generator Agent (Claude-powered analysis with MCP tools)
- Agent Gateway (SSE streaming for real-time events)
- Opportunity Scorer (multi-factor: confidence, return, consensus, volatility, freshness)
- Portfolio risk sizing logic (2% max risk per position)
- Strategy confidence scoring
- Multi-channel delivery specs (Telegram, Discord, Slack, Push, Email)
- Strategy Monitor web dashboard (HTML5/Chart.js)

### What's Missing for Revenue
- **User authentication** — no login, accounts, or API keys
- **Payment processing** — no subscription management or billing
- **Signal delivery** — notifications designed but not wired end-to-end
- **User-facing UI** — no account management, no billing, no portfolio views
- **Compliance** — no disclaimers, ToS, or consent flows

---

## Target Product: TradeStream Signals

**Value proposition**: AI-powered crypto trading signals backed by 40M+ genetically-optimized strategies — not LLM opinion, real quantitative analysis.

**What people pay for**: A Telegram bot + web dashboard that delivers actionable trading signals with confidence scores, entry/exit levels, and the quantitative reasoning behind each signal.

### Pricing Model
| Tier | Price | Includes |
|------|-------|----------|
| **Free** | $0/mo | 3 signals/week, delayed 15 min, top-5 symbols only |
| **Pro** | $49/mo | Unlimited real-time signals, all symbols, Telegram + Discord + email delivery |
| **API** | $149/mo | Everything in Pro + REST API access, webhooks, custom filters |

### Why This Product (Not Live Trading)
1. **Fastest to revenue** — no broker integration, no custody risk, no regulatory burden
2. **Leverages existing strength** — 40M strategies + signal generation is the core IP
3. **Lower liability** — "signals, not financial advice" is a well-understood model
4. **Proven market** — competitors (CryptoSignals, Clawdbot) charge $30-100/mo for inferior signals
5. **Upsell path** — live trading automation becomes the premium tier later

---

## 8-Week Sprint Breakdown

### Week 1: Signal Pipeline End-to-End (Foundation)
**Goal**: Signals flow from strategy engine to a Telegram channel

**Deliverables**:
- [ ] Deploy `signal_generator_agent` to production Kubernetes
- [ ] Deploy `agent_gateway` for SSE streaming
- [ ] Wire opportunity scorer to filter top signals (confidence > 70%)
- [ ] Deploy Telegram bot with basic `/signals` and `/subscribe` commands
- [ ] Manual smoke test: trigger signal → see it in Telegram
- [ ] Set up signal delivery monitoring (Prometheus metrics)

**Key Metric**: First real signal delivered to Telegram

---

### Week 2: Signal Quality & Confidence
**Goal**: Signals are trustworthy enough to show paying users

**Deliverables**:
- [ ] Deploy `strategy_confidence_scorer` to production
- [ ] Implement walk-forward validation gate (only signals from validated strategies)
- [ ] Add multi-strategy consensus requirement (≥3 strategies must agree)
- [ ] Format signals with: symbol, direction, confidence %, entry zone, stop-loss, take-profit
- [ ] Add "not financial advice" disclaimer to every signal
- [ ] Track signal accuracy: compare signal predictions to actual price movement after 24h/48h/7d
- [ ] Build signal accuracy dashboard (internal, for tuning)

**Key Metric**: Signal accuracy tracking live, >55% directional accuracy

---

### Week 3: User Authentication & Accounts
**Goal**: Users can sign up, log in, and have an identity

**Deliverables**:
- [ ] Add authentication service (OAuth2 with Google + email/password)
- [ ] User database schema: `users`, `user_preferences`, `api_keys`
- [ ] JWT token issuance and validation middleware
- [ ] User registration flow (email verification)
- [ ] Telegram bot: `/register` command links Telegram account to TradeStream account
- [ ] Basic account settings API (symbol watchlist, quiet hours)
- [ ] Rate limiting per user tier (free vs. pro)

**Key Metric**: Users can register and link their Telegram account

---

### Week 4: Payment & Subscription Management
**Goal**: Users can pay for Pro tier

**Deliverables**:
- [ ] Stripe integration: subscription creation, webhook handling
- [ ] Billing database schema: `subscriptions`, `invoices`, `payment_methods`
- [ ] Subscription lifecycle: trial → active → past_due → canceled
- [ ] Free tier enforcement: 3 signals/week, 15-min delay, top-5 symbols
- [ ] Pro tier unlock: unlimited signals, all symbols, real-time delivery
- [ ] Stripe Customer Portal for self-service billing management
- [ ] Payment failure handling (grace period, dunning emails)

**Key Metric**: First paying subscriber

---

### Week 5: Web Dashboard MVP
**Goal**: Users have a web interface to manage signals and view performance

**Deliverables**:
- [ ] Landing page with value prop, pricing, and signup CTA
- [ ] Login/signup pages (OAuth2 flow)
- [ ] Signal feed: real-time signal cards with confidence, entry/exit, reasoning
- [ ] Signal history: searchable table of past signals with outcome tracking
- [ ] Account settings: notification preferences, symbol watchlist, quiet hours
- [ ] Subscription management: current plan, upgrade/downgrade, billing history
- [ ] Mobile-responsive design (most crypto traders use mobile)

**Key Metric**: Users can manage their entire subscription from the web

---

### Week 6: Multi-Channel Delivery & Discord
**Goal**: Signals reach users wherever they are

**Deliverables**:
- [ ] Deploy `notification_service` with channel routing logic
- [ ] Discord bot: signal delivery to user DMs and server channels
- [ ] Email digest: daily summary of signals and outcomes (SendGrid)
- [ ] Push notifications: PWA web push for dashboard users
- [ ] Per-user channel preferences (Telegram + email, Discord only, etc.)
- [ ] Cross-channel deduplication (same signal, multiple channels, one alert)
- [ ] Delivery tracking: confirm signals reached users, retry on failure

**Key Metric**: Signals delivered across 3+ channels with >99% delivery rate

---

### Week 7: API Tier & Developer Experience
**Goal**: API tier is live for programmatic users and integrators

**Deliverables**:
- [ ] REST API for signals: `GET /signals`, `GET /signals/:id`, `GET /signals/stream` (SSE)
- [ ] API key management: generation, revocation, usage tracking
- [ ] Rate limiting: 100 req/min for API tier
- [ ] Webhook delivery: push signals to user-configured endpoints
- [ ] API documentation (OpenAPI spec + interactive docs)
- [ ] Usage metering and billing per API call beyond quota
- [ ] SDK starter examples (Python, JavaScript)

**Key Metric**: API tier functional with documentation

---

### Week 8: Polish, Monitoring & Launch Prep
**Goal**: Production-hardened, ready for public launch

**Deliverables**:
- [ ] End-to-end load testing (simulate 500 concurrent users)
- [ ] Error alerting: PagerDuty/Slack for pipeline failures
- [ ] Signal latency optimization (target: <30s from market event to delivery)
- [ ] Terms of Service and Privacy Policy pages
- [ ] Onboarding flow: guided setup for new users (choose symbols, connect Telegram)
- [ ] Referral system: "give a friend 1 week free Pro"
- [ ] Landing page SEO and social meta tags
- [ ] Product Hunt / Hacker News launch prep
- [ ] Public launch announcement

**Key Metric**: Public launch with paying users

---

## Dependencies & Risks

### External Dependencies
| Dependency | Risk | Mitigation |
|-----------|------|------------|
| **Stripe** | API changes, account approval delays | Apply for Stripe account in Week 1, use test mode until approved |
| **Telegram Bot API** | Rate limits (30 msg/sec) | Batch signals, queue delivery, respect limits |
| **OpenRouter/Claude API** | Cost per signal generation | Cache agent reasoning, batch symbol analysis, set cost caps |
| **Exchange APIs (CCXT)** | Rate limits, downtime | Multi-exchange fallback already implemented |
| **Kubernetes cluster** | Scaling costs as users grow | Start with minimal replicas, auto-scale on demand |

### Technical Risks
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Signal generation latency too high | Medium | High | Pre-compute signals on schedule (every 5 min), not on-demand |
| LLM costs exceed revenue per user | Medium | High | Batch analysis (analyze all symbols per run), cache results, use cheaper models for low-confidence signals |
| Strategy performance degrades in live markets | Medium | Medium | Walk-forward validation gate, continuous backtesting, confidence decay over time |
| Auth system security vulnerabilities | Low | Critical | Use battle-tested OAuth library (Keycloak or Auth0), security audit before launch |
| Kafka/Flink pipeline instability | Low | High | Already running 240+ days; add circuit breakers and dead-letter queues |

### Business Risks
| Risk | Mitigation |
|------|------------|
| **Regulatory exposure** | Clear "not financial advice" disclaimers, no custody of funds, no order execution |
| **Signal accuracy expectations** | Publish historical accuracy transparently, set realistic expectations in onboarding |
| **Competitor feature parity** | Focus on quantitative backing (40M strategies) as differentiator, not feature count |
| **Churn after free trial** | Track signal-to-trade conversion, optimize signal quality before scaling acquisition |

---

## Success Criteria (End of Week 8)

| Metric | Target |
|--------|--------|
| Registered users | 200+ |
| Paying subscribers (Pro) | 20+ |
| Monthly recurring revenue | $1,000+ |
| Signal accuracy (directional, 24h) | >55% |
| Signal delivery success rate | >99% |
| Average signal latency | <30 seconds |
| Uptime | >99.5% |

---

## Post-Sprint Roadmap (Weeks 9-16)

Once revenue is established, the next phase focuses on growth and retention:

1. **Paper Trading Mode** — let users "follow" signals with simulated trades to build trust before subscribing
2. **Strategy Leaderboard** — public ranking of top-performing strategies drives organic traffic
3. **Live Trading Integration** — Alpaca/Kraken API for automated execution (Premium tier at $299/mo)
4. **Custom Strategy Requests** — users can request GA optimization for specific symbols/parameters
5. **Community Features** — signal voting, user-submitted strategies, discussion threads
6. **Mobile App** — native iOS/Android for push notification reliability and better UX
