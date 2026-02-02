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

### Default Strategy Types

The following strategy types are available by default:

| Strategy Type | Description | Example Strategies |
|---------------|-------------|-------------------|
| **momentum** | Trades based on price momentum and velocity | RSI, MACD, Stochastic |
| **mean-reversion** | Trades when price deviates from average | Bollinger Bands, RSI Oversold/Overbought |
| **breakout** | Trades when price breaks support/resistance | Donchian Channel, ATR Breakout |
| **trend-following** | Follows established price trends | Moving Average Crossover, ADX |
| **volatility** | Trades based on volatility patterns | ATR, Keltner Channel |
| **volume-based** | Uses volume to confirm signals | OBV, Volume Profile |

### Risk Tolerance Presets

| Preset | Min Confidence | Min Opportunity | Alert on HOLD | Volatility Weight |
|--------|----------------|-----------------|---------------|-------------------|
| **Conservative** | 80% | 75 | No | Lower (10%) |
| **Moderate** | 70% | 60 | No | Normal (15%) |
| **Aggressive** | 50% | 40 | Yes | Higher (20%) |

\`\`\`python
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
\`\`\`

## Database Schema

\`\`\`sql
-- User settings with versioning for concurrency control
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
    version INTEGER DEFAULT 1,  -- For optimistic locking
    last_modified_by VARCHAR(100),  -- Client ID for conflict resolution
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
\`\`\`

## User Settings Migration Strategy

### Problem
When system presets change (e.g., risk tolerance weight adjustments), users who selected those presets may experience silent changes to their trading behavior.

### Solution: Versioned Presets with User Notification

\`\`\`sql
-- Track preset versions
CREATE TABLE preset_versions (
    preset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preset_name VARCHAR(50) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    config JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    deprecated_at TIMESTAMP,
    migration_notes TEXT,
    UNIQUE(preset_name, version)
);

-- Track user's selected preset version
CREATE TABLE user_preset_selections (
    user_id UUID NOT NULL,
    preset_name VARCHAR(50) NOT NULL,
    selected_version INTEGER NOT NULL,
    locked BOOLEAN DEFAULT FALSE,  -- User chose to lock to this version
    last_notified_version INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, preset_name)
);
\`\`\`

### Migration Workflow

\`\`\`python
async def handle_preset_update(preset_name: str, new_config: dict, migration_notes: str):
    """Handle preset configuration update with user notification."""
    # 1. Get current version
    current = await db.fetchrow("""
        SELECT version, config FROM preset_versions
        WHERE preset_name = \$1
        ORDER BY version DESC LIMIT 1
    """, preset_name)

    current_version = current['version'] if current else 0
    new_version = current_version + 1

    # 2. Create new version
    await db.execute("""
        INSERT INTO preset_versions (preset_name, version, config, migration_notes)
        VALUES (\$1, \$2, \$3, \$4)
    """, preset_name, new_version, json.dumps(new_config), migration_notes)

    # 3. Find affected users (not locked)
    affected_users = await db.fetch("""
        SELECT user_id, selected_version FROM user_preset_selections
        WHERE preset_name = \$1
          AND locked = FALSE
          AND selected_version < \$2
    """, preset_name, new_version)

    # 4. Queue notifications for affected users
    for user in affected_users:
        await queue_preset_update_notification(
            user_id=user['user_id'],
            preset_name=preset_name,
            old_version=user['selected_version'],
            new_version=new_version,
            changes=compute_config_diff(current['config'] if current else {}, new_config)
        )

    return new_version
\`\`\`

### User Options for Preset Updates

1. **Auto-update (default)**: User receives notification but is automatically migrated to new version
2. **Lock version**: User explicitly locks to current version, receives warning about outdated preset
3. **Custom**: User has modified preset values, never auto-migrated

## Concurrency Handling

### Problem
Multiple browser tabs or devices editing settings simultaneously can cause conflicts and data loss.

### Solution: Optimistic Locking with Version Numbers

\`\`\`python
from fastapi import HTTPException

async def update_user_settings(
    user_id: str,
    settings: dict,
    expected_version: int,
    client_id: str  # Unique identifier for browser tab/device
) -> dict:
    """Update settings with optimistic concurrency control."""

    # Attempt atomic update with version check
    result = await db.fetchrow("""
        UPDATE user_settings
        SET
            risk_tolerance = COALESCE(\$1, risk_tolerance),
            min_opportunity_score = COALESCE(\$2, min_opportunity_score),
            theme = COALESCE(\$3, theme),
            version = version + 1,
            updated_at = NOW(),
            last_modified_by = \$4
        WHERE user_id = \$5 AND version = \$6
        RETURNING *
    """, settings.get('risk_tolerance'), settings.get('min_opportunity_score'),
        settings.get('theme'), client_id, user_id, expected_version)

    if result is None:
        # Version mismatch - concurrent modification detected
        current = await db.fetchrow("""
            SELECT * FROM user_settings WHERE user_id = \$1
        """, user_id)

        if current is None:
            raise HTTPException(status_code=404, detail="User settings not found")

        raise HTTPException(
            status_code=409,
            detail={
                "error": "CONCURRENT_MODIFICATION",
                "message": "Settings were modified by another session",
                "current_version": current['version'],
                "expected_version": expected_version,
                "last_modified_at": current['updated_at'].isoformat(),
                "last_modified_by": current['last_modified_by'],
                "current_settings": dict(current)
            }
        )

    return dict(result)
\`\`\`

### Client-Side Conflict Resolution

\`\`\`typescript
interface ConflictError {
  error: 'CONCURRENT_MODIFICATION';
  message: string;
  current_version: number;
  expected_version: number;
  last_modified_at: string;
  last_modified_by: string;
  current_settings: UserSettings;
}

type ConflictResolution = 'keep_local' | 'keep_remote' | 'merge';

async function saveSettingsWithConflictHandling(
  settings: UserSettings,
  onConflict: (local: UserSettings, remote: UserSettings) => Promise<ConflictResolution>
): Promise<UserSettings> {
  try {
    return await api.updateSettings(settings);
  } catch (error) {
    if (error.response?.status === 409) {
      const conflict: ConflictError = error.response.data.detail;
      const resolution = await onConflict(settings, conflict.current_settings);

      switch (resolution) {
        case 'keep_local':
          // Retry with current version (force overwrite)
          return await api.updateSettings({
            ...settings,
            version: conflict.current_version
          });
        case 'keep_remote':
          return conflict.current_settings;
        case 'merge':
          const merged = mergeSettings(settings, conflict.current_settings);
          return await api.updateSettings({
            ...merged,
            version: conflict.current_version
          });
      }
    }
    throw error;
  }
}
\`\`\`

### Real-time Sync Across Tabs

For users with multiple tabs open, WebSocket notifications prevent conflicts proactively:

\`\`\`python
async def broadcast_settings_change(user_id: str, client_id: str, new_version: int):
    """Notify other tabs/devices of settings change."""
    await websocket_manager.broadcast_to_user(
        user_id=user_id,
        exclude_client=client_id,  # Don't notify the originator
        message={
            "type": "SETTINGS_UPDATED",
            "version": new_version,
            "action": "RELOAD_SETTINGS"
        }
    )
\`\`\`

## Saved Views

### View Structure

\`\`\`json
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
\`\`\`

### Generative Views (AI-Created)

Users can describe a view in natural language:

\`\`\`
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
\`\`\`

### AI View Validation with Pydantic

Natural language view generation requires strict validation before persisting:

\`\`\`python
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal
from enum import Enum

class StrategyType(str, Enum):
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean-reversion"
    BREAKOUT = "breakout"
    TREND_FOLLOWING = "trend-following"
    VOLATILITY = "volatility"
    VOLUME_BASED = "volume-based"

class ActionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

class ViewFilters(BaseModel):
    """Validated filters for a saved view."""
    symbols: Optional[List[str]] = Field(
        default=None,
        description="Trading pairs to filter by",
        max_items=20
    )
    strategy_types: Optional[List[StrategyType]] = Field(
        default=None,
        description="Strategy types to include"
    )
    min_opportunity_score: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Minimum opportunity score"
    )
    min_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold"
    )
    actions: Optional[List[ActionType]] = Field(
        default=None,
        description="Signal actions to include"
    )

    @validator('symbols', each_item=True)
    def validate_symbol_format(cls, v):
        """Ensure symbols follow BASE/QUOTE format."""
        if v and '/' not in v:
            raise ValueError(f"Invalid symbol format: {v}. Expected BASE/QUOTE (e.g., ETH/USD)")
        return v.upper()

class ViewLayout(BaseModel):
    """Validated layout configuration."""
    panels: Optional[List[dict]] = None
    sort_by: Literal["opportunity_score", "confidence", "created_at"] = "opportunity_score"
    expanded_by_default: bool = False

class GeneratedViewInput(BaseModel):
    """Validated input for AI-generated views."""
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    filters: ViewFilters
    layout: Optional[ViewLayout] = None

class ViewPreview(BaseModel):
    """Preview result before saving."""
    valid: bool
    view: Optional[GeneratedViewInput] = None
    warnings: List[str] = []
    errors: List[dict] = []
    matching_signals_count: Optional[int] = None
\`\`\`

### Preview Step for AI-Generated Views

Before persisting AI-generated views, a preview step validates and shows users what will be saved:

\`\`\`python
from pydantic import ValidationError

async def preview_generated_view(
    user_id: str,
    description: str
) -> ViewPreview:
    """Generate, validate, and preview a view before saving."""

    # 1. Generate view from natural language
    prompt = f"""
    Parse this view description into filters:
    "{description}"

    Available filters:
    - symbols: list of trading pairs (ETH/USD, BTC/USD, etc.)
    - strategy_types: momentum, mean-reversion, breakout, trend-following, volatility, volume-based
    - min_opportunity_score: 0-100
    - min_confidence: 0.0-1.0
    - actions: BUY, SELL, HOLD

    Return valid JSON only:
    {{"name": "...", "filters": {{...}}}}
    """

    response = await llm.complete(prompt)

    try:
        raw_data = json.loads(response)
    except json.JSONDecodeError as e:
        return ViewPreview(
            valid=False,
            errors=[{"type": "json_parse_error", "message": str(e)}]
        )

    # 2. Validate with Pydantic
    try:
        validated_view = GeneratedViewInput(**raw_data)
    except ValidationError as e:
        return ViewPreview(
            valid=False,
            errors=e.errors()
        )

    # 3. Check for warnings
    warnings = []
    if validated_view.filters.symbols and len(validated_view.filters.symbols) == 1:
        warnings.append("Single symbol selected - view may show limited results")
    if validated_view.filters.min_confidence and validated_view.filters.min_confidence > 0.9:
        warnings.append("Very high confidence threshold may result in few signals")
    if validated_view.filters.min_opportunity_score and validated_view.filters.min_opportunity_score > 90:
        warnings.append("Very high opportunity score threshold may result in few signals")

    # 4. Count matching signals for preview
    matching_count = await count_matching_signals(user_id, validated_view.filters)

    return ViewPreview(
        valid=True,
        view=validated_view,
        warnings=warnings,
        matching_signals_count=matching_count
    )


async def save_generated_view(
    user_id: str,
    preview: ViewPreview
) -> dict:
    """Save a previewed and validated view."""
    if not preview.valid or not preview.view:
        raise ValueError("Cannot save invalid view")

    return await db.fetchrow("""
        INSERT INTO user_saved_views (user_id, name, description, filters, layout)
        VALUES (\$1, \$2, \$3, \$4, \$5)
        RETURNING *
    """,
        user_id,
        preview.view.name,
        preview.view.description,
        json.dumps(preview.view.filters.dict(exclude_none=True)),
        json.dumps(preview.view.layout.dict() if preview.view.layout else None)
    )
\`\`\`

## API Endpoints

### Settings

\`\`\`
GET  /api/user/settings
PUT  /api/user/settings

# Request body for PUT (includes version for optimistic locking)
{
  "risk_tolerance": "moderate",
  "min_opportunity_score": 70,
  "theme": "dark",
  "timezone": "America/New_York",
  "version": 5
}

# Response includes new version
{
  "user_id": "...",
  "risk_tolerance": "moderate",
  "version": 6,
  ...
}
\`\`\`

### Watchlist

\`\`\`
GET    /api/user/watchlist
POST   /api/user/watchlist          # Add symbol
DELETE /api/user/watchlist/{symbol} # Remove symbol

# Request body for POST
{
  "symbol": "ETH/USD"
}
\`\`\`

### Strategy Types

\`\`\`
GET  /api/user/strategy-types
PUT  /api/user/strategy-types

# Request body for PUT
{
  "enabled": ["momentum", "breakout"],
  "disabled": ["mean-reversion"]
}
\`\`\`

### Saved Views

\`\`\`
GET    /api/user/views
POST   /api/user/views
GET    /api/user/views/{view_id}
PUT    /api/user/views/{view_id}
DELETE /api/user/views/{view_id}
POST   /api/user/views/preview   # Preview AI-generated view
POST   /api/user/views/generate  # Save previewed view

# Preview request body
{
  "description": "ETH momentum signals with high confidence"
}

# Preview response
{
  "valid": true,
  "view": {
    "name": "ETH High-Confidence Momentum",
    "filters": {...}
  },
  "warnings": ["Single symbol selected - view may show limited results"],
  "matching_signals_count": 12
}

# Generate/save request body (after preview)
{
  "preview_id": "preview-123",
  "confirm": true
}
\`\`\`

### Preset Management

\`\`\`
GET  /api/user/presets/{preset_name}/versions  # Get version history
POST /api/user/presets/{preset_name}/lock      # Lock to current version
POST /api/user/presets/{preset_name}/migrate   # Migrate to specific version

# Migrate request body
{
  "target_version": 3
}
\`\`\`

## UI Components

### Settings Panel

\`\`\`tsx
// components/SettingsPanel/SettingsPanel.tsx

export function SettingsPanel() {
  const { settings, updateSettings, version } = useUserSettings();
  const [conflictModal, setConflictModal] = useState<ConflictState | null>(null);

  const handleUpdate = async (updates: Partial<UserSettings>) => {
    try {
      await updateSettings({ ...updates, version });
    } catch (error) {
      if (error.response?.status === 409) {
        setConflictModal({
          local: { ...settings, ...updates },
          remote: error.response.data.detail.current_settings
        });
      }
    }
  };

  return (
    <div className="settings-panel">
      <Section title="Risk Tolerance">
        <RadioGroup
          value={settings.risk_tolerance}
          onChange={(value) => handleUpdate({ risk_tolerance: value })}
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
          onChange={(value) => handleUpdate({ min_opportunity_score: value })}
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

      {conflictModal && (
        <ConflictResolutionModal
          local={conflictModal.local}
          remote={conflictModal.remote}
          onResolve={(resolution) => {
            handleConflictResolution(resolution);
            setConflictModal(null);
          }}
          onCancel={() => setConflictModal(null)}
        />
      )}
    </div>
  );
}
\`\`\`

### Saved Views Selector with Preview

\`\`\`tsx
// components/ViewSelector/ViewSelector.tsx

export function ViewSelector() {
  const { views, activeView, setActiveView } = useSavedViews();
  const [isCreating, setIsCreating] = useState(false);
  const [description, setDescription] = useState('');
  const [preview, setPreview] = useState<ViewPreview | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const handlePreviewView = async () => {
    setIsGenerating(true);
    try {
      const previewResult = await api.previewView({ description });
      setPreview(previewResult);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleConfirmSave = async () => {
    if (!preview?.valid) return;
    const savedView = await api.saveView(preview);
    setActiveView(savedView.view_id);
    setIsCreating(false);
    setPreview(null);
    setDescription('');
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
        <Dialog onClose={() => { setIsCreating(false); setPreview(null); }}>
          <Input
            label="Describe your view"
            placeholder="e.g., ETH signals from momentum strategies"
            value={description}
            onChange={setDescription}
          />

          <Button onClick={handlePreviewView} disabled={isGenerating}>
            {isGenerating ? 'Generating...' : 'Preview View'}
          </Button>

          {preview && (
            <div className="view-preview">
              {preview.valid ? (
                <>
                  <h4>Preview: {preview.view.name}</h4>
                  <pre>{JSON.stringify(preview.view.filters, null, 2)}</pre>

                  {preview.warnings.length > 0 && (
                    <div className="warnings">
                      {preview.warnings.map((w, i) => (
                        <p key={i} className="warning">{w}</p>
                      ))}
                    </div>
                  )}

                  <p>Matching signals: {preview.matching_signals_count}</p>

                  <Button onClick={handleConfirmSave}>
                    Save View
                  </Button>
                </>
              ) : (
                <div className="errors">
                  <p>Could not generate view:</p>
                  {preview.errors.map((e, i) => (
                    <p key={i} className="error">{e.message || e.msg}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </Dialog>
      )}
    </div>
  );
}
\`\`\`

## Applying Preferences

### Signal Filtering

\`\`\`python
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
\`\`\`

### Custom Scoring Weights

\`\`\`python
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
\`\`\`

## Configuration

\`\`\`yaml
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
    settings_sync: true  # Cross-device sync via WebSocket

  preset_migration:
    auto_migrate_unlocked: true
    notify_before_migration: true
    allow_version_lock: true
\`\`\`

## Constraints

- Settings persisted in PostgreSQL
- Anonymous users get defaults
- Changes apply immediately (no page refresh)
- Saved views limited to 10 per user
- Watchlist limited to 20 symbols
- AI-generated views require preview step before saving
- Concurrent edits handled via optimistic locking

## Acceptance Criteria

- [ ] Users can filter signals by symbol
- [ ] Users can set minimum opportunity score
- [ ] Risk tolerance presets work correctly
- [ ] Users can save custom views
- [ ] AI-generated views from natural language work with validation
- [ ] AI-generated views show preview before saving
- [ ] Settings persist across sessions
- [ ] Changes apply immediately without refresh
- [ ] Anonymous users see default settings
- [ ] API endpoints return appropriate errors
- [ ] Concurrent edits show conflict resolution UI
- [ ] Preset version changes notify affected users
- [ ] Users can lock to specific preset versions

## File Structure

\`\`\`
services/user_service/
├── __init__.py
├── main.py
├── routes/
│   ├── settings.py
│   ├── watchlist.py
│   ├── strategy_types.py
│   ├── views.py
│   └── presets.py
├── services/
│   ├── settings_service.py
│   ├── view_generator.py
│   ├── view_validator.py
│   ├── filter_service.py
│   ├── preset_migration.py
│   └── conflict_resolver.py
├── models/
│   ├── user.py
│   ├── view.py
│   └── preset.py
└── tests/
    ├── test_settings.py
    ├── test_view_validation.py
    ├── test_concurrency.py
    └── test_preset_migration.py

ui/agent-dashboard/src/
├── components/
│   ├── SettingsPanel/
│   │   ├── SettingsPanel.tsx
│   │   ├── RiskToleranceSelector.tsx
│   │   ├── SymbolSelector.tsx
│   │   └── ConflictResolutionModal.tsx
│   └── ViewSelector/
│       ├── ViewSelector.tsx
│       └── ViewPreview.tsx
├── hooks/
│   ├── useUserSettings.ts
│   ├── useSavedViews.ts
│   └── useSettingsSync.ts
└── api/
    └── user.ts
\`\`\`
