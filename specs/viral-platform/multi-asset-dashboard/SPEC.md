# Multi-Asset Trading Signal Dashboard - UI Specification

## Overview

This specification defines the UI design system for TradeStream's multi-asset trading signal dashboard. The dashboard displays real-time signals across **7 asset classes**: Crypto, Stocks, Options, ETFs, Forex, and Prediction Markets (Polymarket, Kalshi).

## Design Philosophy

### Core Principles

1. **Data Density with Clarity** - Trading dashboards require high information density, but with clear visual hierarchy
2. **Minimal Color Palette** - Reduce cognitive load with strategic, purposeful color use
3. **Accessibility First** - WCAG AA compliant, colorblind-safe indicators
4. **Progressive Disclosure** - Show essential info upfront, details on interaction

### Inspired By

- [moomoo](https://moomoo.com) - Clean, professional trading interface
- Bloomberg Terminal - Data density, keyboard navigation
- TradingView - Chart integration, social features

---

## Color System

### Background Palette (Dark Theme)

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-primary` | `#0a0a0b` | Main background |
| `--bg-secondary` | `#111113` | Cards, panels |
| `--bg-tertiary` | `#18181b` | Hover states, nested elements |
| `--border` | `#27272a` | Borders, dividers |

### Text Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `--text-primary` | `#fafafa` | Headings, primary content |
| `--text-secondary` | `#a1a1aa` | Body text, descriptions |
| `--text-muted` | `#52525b` | Timestamps, tertiary info |

### Brand & Accent

| Token | Hex | Usage |
|-------|-----|-------|
| `--accent` | `#06b6d4` | Brand color, interactive elements |

### Semantic Colors (Actions)

| Token | Hex | Usage |
|-------|-----|-------|
| `--positive` | `#22c55e` | Buy signals, gains, success |
| `--negative` | `#ef4444` | Sell signals, losses, errors |
| `--neutral` | `#eab308` | Hold signals, warnings |

### Asset Class Colors (Consolidated - 4 Categories)

Based on UX review, we consolidate 7 asset types into 4 visual categories to reduce cognitive load:

| Category | Asset Types | Hex | Rationale |
|----------|-------------|-----|-----------|
| **Crypto** | Crypto | `#f97316` (Orange) | Distinct, established association |
| **Equities** | Stocks, Options, ETFs | `#a855f7` (Purple) | Related asset classes, differentiated by symbol format |
| **Forex** | Forex | `#3b82f6` (Blue) | Currency pairs, global markets |
| **Predictions** | Polymarket, Kalshi | `#ec4899` (Pink) | Event-based, probability markets |

**Note:** Options are distinguished from Stocks/ETFs by their symbol format (`AAPL 195C 3/15`) rather than color.

### Badge Styling

```css
/* Asset type badges - subtle background with matching text */
.asset-badge {
  font-size: 9px;
  font-weight: 600;
  padding: 3px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.asset-badge.crypto { background: rgba(249, 115, 22, 0.15); color: #f97316; }
.asset-badge.equities { background: rgba(168, 85, 247, 0.15); color: #a855f7; }
.asset-badge.forex { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }
.asset-badge.prediction { background: rgba(236, 72, 153, 0.15); color: #ec4899; }
```

---

## Typography

### Font Stack

```css
font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
```

### Scale

| Element | Size | Weight | Line Height |
|---------|------|--------|-------------|
| Page title | 20px | 600 | 1.2 |
| Card symbol | 16px | 600 | 1.3 |
| Body text | 14px | 400 | 1.5 |
| Secondary text | 13px | 400 | 1.5 |
| Labels/badges | 11px | 600 | 1.2 |
| Micro text | 10px | 500 | 1.2 |

### Numeric Display

- **Scores**: Display as percentage (87%) not decimal (0.87) for instant comprehension
- **Prices**: Use locale-appropriate formatting with currency symbol
- **Probabilities**: Display as percentage with % symbol for prediction markets

---

## Signal Card Component

### Information Hierarchy

1. **Primary** (instant scan): Asset Type -> Action -> Symbol -> Score
2. **Secondary** (quick read): Price/Probability -> Provider
3. **Tertiary** (on interest): Reasoning -> Metadata -> Timestamps

### Card Layout

```
+-------------------------------------------------------------+
| [CRYPTO]  [^ BUY]  BTC          $67,420           87%      |
|                                                   SCORE    |
+-------------------------------------------------------------+
| CryptoKing_42 . 67% WR . 12.4K                     2m ago  |
+-------------------------------------------------------------+
| RSI oversold bounce with MACD turning positive. 4/5       |
| strategies agree on entry.                                 |
+-------------------------------------------------------------+
```

### Accessibility: Colorblind-Safe Action Indicators

In addition to color, use arrows for buy/sell differentiation:

| Action | Color | Icon | Label |
|--------|-------|------|-------|
| Buy | Green | ^ | "Buy" or "Yes" |
| Sell | Red | v | "Sell" or "No" |
| Hold | Yellow | - | "Hold" |

```tsx
<span className="action-badge buy">
  <span className="action-icon">^</span>
  Buy
</span>
```

### Signal Freshness Indicator

Signals have time decay. Visual freshness helps users prioritize:

| Age | Visual Treatment |
|-----|------------------|
| < 2 min | Subtle cyan border glow, "Just now" |
| 2-10 min | Normal styling, relative time |
| 10-60 min | Slightly muted (opacity: 0.9) |
| > 1 hour | Muted (opacity: 0.7), consider hiding |

```css
.signal-card.fresh {
  border-color: var(--accent);
  box-shadow: 0 0 12px rgba(6, 182, 212, 0.15);
}

.signal-card.stale {
  opacity: 0.7;
}
```

---

## Asset-Specific Display

### Crypto Signals

```
[CRYPTO] [^ BUY]  BTC  $67,420                      87%
```

### Stock Signals

```
[EQUITIES] [^ BUY]  NVDA  $875.40                   81%
```

### Options Signals

Symbol format: `{UNDERLYING} {STRIKE}{C/P} {EXPIRY}`

```
[EQUITIES] [^ BUY]  AAPL 195C 3/15  $4.20          84%
                    Delta: 0.45  Theta: -0.08
```

Options cards include Greeks row when expanded:
- Delta, Gamma, Theta, Vega, IV
- Open Interest, Volume

### ETF Signals

```
[EQUITIES] [^ BUY]  QQQ  $438.50                    80%
```

### Forex Signals

Symbol format: `{BASE}/{QUOTE}`

```
[FOREX] [v SELL]  EUR/USD  1.0842                   77%
```

### Prediction Market Signals

Action uses Yes/No instead of Buy/Sell. Shows probability instead of price.

```
[PREDICTION] [^ YES]  Fed Rate Cut March            79%
                      Currently 68%    [Polymarket]
```

Include:
- Current probability (displayed prominently)
- Platform badge (Polymarket, Kalshi)
- Resolution date (if available)

---

## Filter Bar

### Asset Class Filter

Horizontal pill/chip selector with multi-select:

```
[All] [Crypto] [Equities] [Forex] [Predictions]
```

- "All" is default (no filtering)
- Multiple classes can be selected
- Active state: filled background
- Inactive state: transparent with border

### Action Filter

```
[Buy] [Sell] [Hold]
```

### Score Threshold

Slider from 0-100 (displayed as percentage):

```
Min Score: -----*----- 60%
```

### Search

Text input for symbol/keyword search:
- Searches: symbol, provider name, reasoning text
- Debounced (300ms)

---

## Toast Notifications

New signals trigger toast notifications in bottom-right corner.

### Toast Layout

```
+----------------------------------------+
| [CRYPTO] [^ BUY]  BTC . 87%           |
+----------------------------------------+
```

### Behavior

- Auto-dismiss after 4 seconds
- Max 3 visible toasts (queue additional)
- Click to scroll signal into view
- Swipe/click X to dismiss early

---

## TypeScript Types

### Signal Type (Discriminated Union)

```typescript
type AssetCategory = 'crypto' | 'equities' | 'forex' | 'prediction';
type AssetType = 'crypto' | 'stock' | 'option' | 'etf' | 'forex' | 'prediction';
type SignalAction = 'buy' | 'sell' | 'hold' | 'yes' | 'no';

interface BaseSignal {
  id: string;
  asset_type: AssetType;
  asset_category: AssetCategory; // Derived for color coding
  action: SignalAction;
  symbol: string;
  score: number; // 0-100, displayed as percentage
  provider: Provider;
  reasoning: string;
  created_at: string; // ISO 8601
}

interface CryptoSignal extends BaseSignal {
  asset_type: 'crypto';
  asset_category: 'crypto';
  price: number;
}

interface StockSignal extends BaseSignal {
  asset_type: 'stock';
  asset_category: 'equities';
  price: number;
}

interface OptionSignal extends BaseSignal {
  asset_type: 'option';
  asset_category: 'equities';
  underlying: string;
  strike: number;
  option_type: 'call' | 'put';
  expiry: string; // YYYY-MM-DD
  premium: number;
  greeks?: {
    delta: number;
    gamma: number;
    theta: number;
    vega: number;
    iv: number;
  };
}

interface ETFSignal extends BaseSignal {
  asset_type: 'etf';
  asset_category: 'equities';
  price: number;
}

interface ForexSignal extends BaseSignal {
  asset_type: 'forex';
  asset_category: 'forex';
  rate: number;
  base_currency: string;
  quote_currency: string;
}

interface PredictionSignal extends BaseSignal {
  asset_type: 'prediction';
  asset_category: 'prediction';
  action: 'yes' | 'no';
  probability: number; // 0-1, displayed as percentage
  platform: 'polymarket' | 'kalshi';
  market_question: string;
  resolution_date?: string;
}

type Signal =
  | CryptoSignal
  | StockSignal
  | OptionSignal
  | ETFSignal
  | ForexSignal
  | PredictionSignal;
```

### Provider Type

```typescript
interface Provider {
  id: string;
  name: string;
  win_rate: number; // 0-1, displayed as percentage
  followers: number;
  verified: boolean;
}
```

### Filter State

```typescript
interface SignalFilters {
  asset_categories: AssetCategory[]; // Empty = all
  actions: SignalAction[]; // Empty = all
  min_score: number; // 0-100
  search_query: string;
}
```

---

## API Contract

### SSE Stream Endpoint

```
GET /api/signals/stream
  ?categories=crypto,equities
  &min_score=60
Accept: text/event-stream
```

### Event Types

```
event: signal
id: uuid-here
data: {"asset_type":"crypto","symbol":"BTC",...}

event: heartbeat
data: {"timestamp":"...","connected_providers":42}

event: error
data: {"code":"RATE_LIMITED","retry_after":30}
```

### Signal Response Schema

```json
{
  "id": "uuid",
  "asset_type": "option",
  "asset_category": "equities",
  "action": "buy",
  "symbol": "AAPL 195C 3/15",
  "score": 84,
  "provider": {
    "id": "uuid",
    "name": "OptionsFlow",
    "win_rate": 71,
    "followers": 9200,
    "verified": true
  },
  "reasoning": "Unusual call volume. IV crush opportunity.",
  "asset_data": {
    "underlying": "AAPL",
    "strike": 195,
    "option_type": "call",
    "expiry": "2026-03-15",
    "premium": 4.20,
    "greeks": {
      "delta": 0.45,
      "theta": -0.08,
      "gamma": 0.03,
      "vega": 0.22,
      "iv": 0.32
    }
  },
  "created_at": "2026-02-15T14:32:00Z"
}
```

---

## Component Checklist

### Core Components

- [ ] `SignalCard` - Main signal display with asset-specific variants
- [ ] `SignalFeed` - Virtualized list with SSE updates
- [ ] `FilterBar` - Asset category, action, score, search filters
- [ ] `ToastNotification` - New signal alerts
- [ ] `ToastContainer` - Toast positioning and queue management

### Shared Components

- [ ] `AssetBadge` - Asset category indicator with icon
- [ ] `ActionBadge` - Buy/Sell/Hold with arrow icon
- [ ] `ScoreDisplay` - Percentage score with color coding
- [ ] `ProviderInfo` - Name, win rate, followers, verified badge
- [ ] `RelativeTime` - "2m ago" with freshness styling

### Asset-Specific Components

- [ ] `CryptoSignalContent` - Price display
- [ ] `StockSignalContent` - Price display
- [ ] `OptionSignalContent` - Greeks, expiry, premium
- [ ] `ETFSignalContent` - Price display
- [ ] `ForexSignalContent` - Rate, pair display
- [ ] `PredictionSignalContent` - Probability, platform badge

---

## Verification Criteria

1. **Visual**
   - [ ] All asset types display with correct category color
   - [ ] Score displays as percentage (87% not 0.87)
   - [ ] Buy/Sell have arrow indicators in addition to color
   - [ ] Fresh signals (< 2 min) have subtle glow
   - [ ] Stale signals (> 1 hour) are visually muted

2. **Functional**
   - [ ] SSE stream connects and receives signals
   - [ ] Filters update signal list in real-time
   - [ ] Toast notifications appear for new signals
   - [ ] Filter state persists in URL params

3. **Accessibility**
   - [ ] Color contrast meets WCAG AA (4.5:1 minimum)
   - [ ] Action indicators work without color (arrows)
   - [ ] Screen reader announces new signals
   - [ ] Keyboard navigation works throughout

4. **Performance**
   - [ ] Signal list virtualizes at 100+ items
   - [ ] SSE reconnects automatically on disconnect
   - [ ] Filter changes don't cause layout shift

---

## Appendix: Color Contrast Verification

| Combination | Ratio | WCAG AA |
|-------------|-------|---------|
| #0a0a0b + #fafafa (primary text) | 19.8:1 | Pass |
| #0a0a0b + #a1a1aa (secondary text) | 7.2:1 | Pass |
| #0a0a0b + #22c55e (positive) | 8.1:1 | Pass |
| #0a0a0b + #ef4444 (negative) | 5.8:1 | Pass |
| #0a0a0b + #f97316 (crypto) | 7.9:1 | Pass |
| #0a0a0b + #a855f7 (equities) | 5.2:1 | Pass |
| #0a0a0b + #3b82f6 (forex) | 5.4:1 | Pass |
| #0a0a0b + #ec4899 (prediction) | 6.1:1 | Pass |
