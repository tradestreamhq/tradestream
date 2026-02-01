# User Customization Specification

## Goal

Let users personalize the agent dashboard to their trading style and preferences, including symbol selection, strategy filters, risk tolerance, and saved views.

## Customization Options

### Settings Overview

| Setting | Options | Default | Scope |
|---------|---------|---------|-------|
| **Symbols** | Select from 20 active symbols | All | Signal filtering |
| **Strategy Types** | momentum, mean-reversion, breakout, etc. | All | Signal filtering |
| **Minimum Opportunity Score** | 0-100 slider | 60 | Signal filtering |
| **Risk Tolerance** | Conservative/Moderate/Aggressive | Moderate | Scoring weights |
| **Alert Frequency** | Immediate/Hourly/Daily digest | Immediate | Delivery |
| **Channels** | Web/Telegram/Discord/Slack | Web only | Delivery |
| **Theme** | Dark/Light/System | Dark | UI |

### Risk Tolerance Presets

| Preset | Min Confidence | Min Opportunity | Alert on HOLD | Volatility Weight |
|--------|----------------|-----------------|---------------|-------------------|
| **Conservative** | 80% | 75 | No | Lower (10%) |
| **Moderate** | 70% | 60 | No | Normal (15%) |
| **Aggressive** | 50% | 40 | Yes | Higher (20%) |

```python
RISK_PRESETS = {
    "conservative": {
        "min_confidence": 0.80,
        "min_opportunity_score": 75,
        "alert_on_hold": False,
        "scoring_weights": {
            "confidence": 0.30,      # +5% for conservative
            "expected_return": 0.25, # -5% (less speculative)
            "consensus": 0.25,       # +5% (want agreement)
            "volatility": 0.10,      # -5% (less risk)
            "freshness": 0.10
        }
    },
    "moderate": {
        "min_confidence": 0.70,
        "min_opportunity_score": 60,
        "alert_on_hold": False,
        "scoring_weights": {
            "confidence": 0.25,
            "expected_return": 0.30,
            "consensus": 0.20,
            "volatility": 0.15,
            "freshness": 0.10
        }
    },
    "aggressive": {
        "min_confidence": 0.50,
        "min_opportunity_score": 40,
        "alert_on_hold": True,
        "scoring_weights": {
            "confidence": 0.20,      # -5% (willing to take risks)
            "expected_return": 0.35, # +5% (chasing returns)
            "consensus": 0.15,       # -5% (contrarian ok)
            "volatility": 0.20,      # +5% (likes volatility)
            "freshness": 0.10
        }
    }
}
```

## Database Schema

```sql
-- User settings
CREATE TABLE user_settings (
    user_id UUID PRIMARY KEY,
    email VARCHAR(255),
    risk_tolerance VARCHAR(20) DEFAULT 'moderate',
    min_opportunity_score INTEGER DEFAULT 60,
    min_confidence DECIMAL(3,2) DEFAULT 0.70,
    alert_on_hold BOOLEAN DEFAULT FALSE,
    theme VARCHAR(20) DEFAULT 'dark',
    timezone VARCHAR(50) DEFAULT 'UTC',
    scoring_weights JSONB,  -- Custom weights override preset
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Symbol watchlist
CREATE TABLE user_watchlist (
    user_id UUID NOT NULL REFERENCES user_settings(user_id),
    symbol VARCHAR(50) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    added_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, symbol)
);

-- Strategy type preferences
CREATE TABLE user_strategy_types (
    user_id UUID NOT NULL REFERENCES user_settings(user_id),
    strategy_type VARCHAR(50) NOT NULL,  -- momentum, mean-reversion, etc.
    enabled BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (user_id, strategy_type)
);

-- Saved views
CREATE TABLE user_saved_views (
    view_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_settings(user_id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    filters JSONB NOT NULL,
    layout JSONB,  -- Custom dashboard layout
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_saved_views_user ON user_saved_views(user_id);
```

## Saved Views

### View Structure

```json
{
  "view_id": "view-abc123",
  "name": "My ETH Momentum View",
  "description": "ETH signals from momentum strategies only",
  "filters": {
    "symbols": ["ETH/USD", "ETH/BTC"],
    "strategy_types": ["momentum", "breakout"],
    "min_opportunity_score": 70,
    "actions": ["BUY", "SELL"]
  },
  "layout": {
    "panels": [
      { "type": "signal_stream", "position": "main" },
      { "type": "strategy_performance", "position": "sidebar" }
    ],
    "sort_by": "opportunity_score",
    "expanded_by_default": false
  }
}
```

### Generative Views (AI-Created)

Users can describe a view in natural language:

```
User: "Show me ETH signals from momentum strategies with high confidence"

System creates view:
{
  "name": "ETH High-Confidence Momentum",
  "filters": {
    "symbols": ["ETH/USD"],
    "strategy_types": ["momentum"],
    "min_confidence": 0.80
  }
}
```

### Implementation

```python
async def create_view_from_natural_language(
    user_id: str,
    description: str
) -> SavedView:
    """Use LLM to parse natural language into view filters."""

    prompt = f"""
    Parse this view description into filters:
    "{description}"

    Available filters:
    - symbols: list of trading pairs (ETH/USD, BTC/USD, etc.)
    - strategy_types: momentum, mean-reversion, breakout, trend-following
    - min_opportunity_score: 0-100
    - min_confidence: 0.0-1.0
    - actions: BUY, SELL, HOLD

    Return JSON:
    {{"name": "...", "filters": {{...}}}}
    """

    response = await llm.complete(prompt)
    view_data = json.loads(response)

    return await save_view(user_id, view_data)
```

## API Endpoints

### Settings

```
GET  /api/user/settings
PUT  /api/user/settings

# Request body for PUT
{
  "risk_tolerance": "moderate",
  "min_opportunity_score": 70,
  "theme": "dark",
  "timezone": "America/New_York"
}
```

### Watchlist

```
GET    /api/user/watchlist
POST   /api/user/watchlist          # Add symbol
DELETE /api/user/watchlist/{symbol} # Remove symbol

# Request body for POST
{
  "symbol": "ETH/USD"
}
```

### Strategy Types

```
GET  /api/user/strategy-types
PUT  /api/user/strategy-types

# Request body for PUT
{
  "enabled": ["momentum", "breakout"],
  "disabled": ["mean-reversion"]
}
```

### Saved Views

```
GET    /api/user/views
POST   /api/user/views
GET    /api/user/views/{view_id}
PUT    /api/user/views/{view_id}
DELETE /api/user/views/{view_id}
POST   /api/user/views/generate  # AI-generated from description

# Generate request body
{
  "description": "ETH momentum signals with high confidence"
}
```

## UI Components

### Settings Panel

```tsx
// components/SettingsPanel/SettingsPanel.tsx

export function SettingsPanel() {
  const { settings, updateSettings } = useUserSettings();

  return (
    <div className="settings-panel">
      <Section title="Risk Tolerance">
        <RadioGroup
          value={settings.risk_tolerance}
          onChange={(value) => updateSettings({ risk_tolerance: value })}
          options={[
            { value: 'conservative', label: 'Conservative', description: 'Higher confidence required, lower volatility tolerance' },
            { value: 'moderate', label: 'Moderate (Recommended)', description: 'Balanced approach' },
            { value: 'aggressive', label: 'Aggressive', description: 'Lower thresholds, embraces volatility' }
          ]}
        />
      </Section>

      <Section title="Minimum Opportunity Score">
        <Slider
          min={0}
          max={100}
          value={settings.min_opportunity_score}
          onChange={(value) => updateSettings({ min_opportunity_score: value })}
          markers={[
            { value: 40, label: 'Low' },
            { value: 60, label: 'Good' },
            { value: 80, label: 'Hot' }
          ]}
        />
      </Section>

      <Section title="Symbols">
        <SymbolSelector
          selected={settings.watchlist}
          onChange={(symbols) => updateWatchlist(symbols)}
        />
      </Section>

      <Section title="Strategy Types">
        <CheckboxGroup
          options={STRATEGY_TYPES}
          selected={settings.strategy_types}
          onChange={(types) => updateStrategyTypes(types)}
        />
      </Section>
    </div>
  );
}
```

### Saved Views Selector

```tsx
// components/ViewSelector/ViewSelector.tsx

export function ViewSelector() {
  const { views, activeView, setActiveView, createView } = useSavedViews();
  const [isCreating, setIsCreating] = useState(false);
  const [description, setDescription] = useState('');

  const handleGenerateView = async () => {
    const view = await createView({ description });
    setActiveView(view.view_id);
    setIsCreating(false);
  };

  return (
    <div className="view-selector">
      <Select
        value={activeView}
        onChange={setActiveView}
        options={[
          { value: null, label: 'Default View' },
          ...views.map(v => ({ value: v.view_id, label: v.name }))
        ]}
      />

      <Button onClick={() => setIsCreating(true)}>
        + Create View
      </Button>

      {isCreating && (
        <Dialog onClose={() => setIsCreating(false)}>
          <Input
            label="Describe your view"
            placeholder="e.g., ETH signals from momentum strategies"
            value={description}
            onChange={setDescription}
          />
          <Button onClick={handleGenerateView}>
            Generate View
          </Button>
        </Dialog>
      )}
    </div>
  );
}
```

## Applying Preferences

### Signal Filtering

```python
async def filter_signals_for_user(
    user_id: str,
    signals: list[Signal]
) -> list[Signal]:
    """Apply user preferences to filter signals."""
    settings = await get_user_settings(user_id)
    watchlist = await get_user_watchlist(user_id)
    strategy_types = await get_user_strategy_types(user_id)

    filtered = []
    for signal in signals:
        # Symbol filter
        if watchlist and signal.symbol not in watchlist:
            continue

        # Strategy type filter
        if strategy_types:
            signal_types = [s.strategy_type for s in signal.strategy_breakdown]
            if not any(t in strategy_types for t in signal_types):
                continue

        # Opportunity score filter
        if signal.opportunity_score < settings.min_opportunity_score:
            continue

        # Confidence filter
        if signal.confidence < settings.min_confidence:
            continue

        # HOLD filter
        if signal.action == 'HOLD' and not settings.alert_on_hold:
            continue

        filtered.append(signal)

    return filtered
```

### Custom Scoring Weights

```python
def calculate_opportunity_score_for_user(
    signal: Signal,
    user_settings: UserSettings
) -> float:
    """Calculate opportunity score using user's custom weights."""
    weights = user_settings.scoring_weights or RISK_PRESETS[user_settings.risk_tolerance]["scoring_weights"]

    score = (
        weights["confidence"] * signal.confidence +
        weights["expected_return"] * normalize(signal.expected_return) +
        weights["consensus"] * signal.consensus_pct +
        weights["volatility"] * normalize(signal.volatility) +
        weights["freshness"] * signal.freshness_score
    ) * 100

    return round(score, 1)
```

## Configuration

```yaml
user_customization:
  defaults:
    risk_tolerance: moderate
    min_opportunity_score: 60
    theme: dark
    timezone: UTC

  limits:
    max_watchlist_symbols: 20
    max_saved_views: 10
    max_strategy_types: 10

  features:
    generative_views: true
    custom_scoring_weights: true  # Premium feature?
```

## Constraints

- Settings persisted in PostgreSQL
- Anonymous users get defaults
- Changes apply immediately (no page refresh)
- Saved views limited to 10 per user
- Watchlist limited to 20 symbols

## Acceptance Criteria

- [ ] Users can filter signals by symbol
- [ ] Users can set minimum opportunity score
- [ ] Risk tolerance presets work correctly
- [ ] Users can save custom views
- [ ] AI-generated views from natural language work
- [ ] Settings persist across sessions
- [ ] Changes apply immediately without refresh
- [ ] Anonymous users see default settings
- [ ] API endpoints return appropriate errors

## File Structure

```
services/user_service/
├── __init__.py
├── main.py
├── routes/
│   ├── settings.py
│   ├── watchlist.py
│   ├── strategy_types.py
│   └── views.py
├── services/
│   ├── settings_service.py
│   ├── view_generator.py
│   └── filter_service.py
├── models/
│   └── user.py
└── tests/
    └── test_settings.py

ui/agent-dashboard/src/
├── components/
│   ├── SettingsPanel/
│   │   ├── SettingsPanel.tsx
│   │   ├── RiskToleranceSelector.tsx
│   │   └── SymbolSelector.tsx
│   └── ViewSelector/
│       └── ViewSelector.tsx
├── hooks/
│   ├── useUserSettings.ts
│   └── useSavedViews.ts
└── api/
    └── user.ts
```
