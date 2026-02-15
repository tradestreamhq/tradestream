# Strategy Database Specification

## Goal

Database layer for strategy specs (the "what") and implementations (the "values"), seeded from existing YAML configs and supporting the full strategy lifecycle from discovery to retirement.

## Two-Part Model

```
SPEC (Structure)                    IMPLEMENTATION (Values)
─────────────────────────────────   ───────────────────────────────────
• Name: RSI_REVERSAL                • Spec: RSI_REVERSAL
• Indicators: [RSI]                 • Parameters: {rsiPeriod: 14, oversold: 30}
• Entry: RSI < oversold             • Performance: {sharpe: 1.8, accuracy: 62%}
• Exit: RSI > overbought            • Symbol: ETH/USD
• Parameter ranges:                 • Discovered: 2025-08-15
  - rsiPeriod: 5-50                 • Status: VALIDATED
  - oversold: 20-35                 • Signals: 847
• Source: CANONICAL (from YAML)
```

### Why Separate Specs and Implementations?

1. **Reusability**: One spec can have thousands of implementations with different parameters
2. **Traceability**: Know which strategies came from original YAML vs. LLM-generated
3. **Lifecycle Management**: Track validation status independently
4. **Learning Agent**: Generate new specs based on top performers

## Database Schema

### Strategy Specs

```sql
CREATE TABLE strategy_specs (
    spec_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    version INTEGER DEFAULT 1,
    description TEXT,

    -- Strategy definition
    indicators JSONB NOT NULL,       -- [{type: "RSI", params: {period: "${rsiPeriod}"}}]
    entry_conditions JSONB NOT NULL, -- [{type: "UNDER_CONSTANT", indicator: "rsi", value: "${oversold}"}]
    exit_conditions JSONB NOT NULL,  -- [{type: "OVER_CONSTANT", indicator: "rsi", value: "${overbought}"}]

    -- Parameter definitions
    parameters JSONB NOT NULL,       -- [{name: "rsiPeriod", type: "INTEGER", min: 5, max: 50, defaultValue: 14}]

    -- Metadata
    source VARCHAR(50) NOT NULL,     -- CANONICAL, LLM_GENERATED, USER_CREATED
    source_file VARCHAR(255),        -- Original YAML file path for CANONICAL
    reasoning TEXT,                  -- Why this spec was created (for LLM_GENERATED)

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    retired_at TIMESTAMP,
    retired_reason TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- B-tree indexes for equality/range queries
CREATE INDEX idx_specs_source ON strategy_specs(source);
CREATE INDEX idx_specs_active ON strategy_specs(is_active);

-- GIN indexes for JSONB columns (efficient queries by indicator type, condition type, etc.)
CREATE INDEX idx_specs_indicators_gin ON strategy_specs USING GIN (indicators);
CREATE INDEX idx_specs_entry_conditions_gin ON strategy_specs USING GIN (entry_conditions);
CREATE INDEX idx_specs_exit_conditions_gin ON strategy_specs USING GIN (exit_conditions);
CREATE INDEX idx_specs_parameters_gin ON strategy_specs USING GIN (parameters);
```

#### Example JSONB Queries with GIN Indexes

```sql
-- Find all specs using RSI indicator
SELECT * FROM strategy_specs
WHERE indicators @> '[{"type": "RSI"}]';

-- Find specs with CROSSED_UP entry conditions
SELECT * FROM strategy_specs
WHERE entry_conditions @> '[{"type": "CROSSED_UP"}]';

-- Find specs that have a specific parameter
SELECT * FROM strategy_specs
WHERE parameters @> '[{"name": "rsiPeriod"}]';
```

### Strategy Implementations

```sql
CREATE TABLE strategy_implementations (
    impl_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    spec_id UUID NOT NULL REFERENCES strategy_specs(spec_id),

    -- Configuration
    parameters JSONB NOT NULL,       -- {rsiPeriod: 14, oversold: 30, overbought: 70}
    symbol VARCHAR(50) NOT NULL,

    -- Discovery metadata
    discovered_by VARCHAR(50),       -- GA_OPTIMIZED, LLM_SUGGESTED, MANUAL
    generation INTEGER,              -- GA generation number (if applicable)
    parent_impl_id UUID,             -- Parent implementation (if evolved from)

    -- Backtest metrics (from initial optimization)
    backtest_sharpe DECIMAL(8,4),
    backtest_accuracy DECIMAL(5,4),
    backtest_return DECIMAL(8,4),
    backtest_max_drawdown DECIMAL(5,4),
    backtest_trades INTEGER,
    backtest_start_date DATE,
    backtest_end_date DATE,

    -- Forward test metrics (from paper trading)
    forward_sharpe DECIMAL(8,4),
    forward_accuracy DECIMAL(5,4),
    forward_return DECIMAL(8,4),
    forward_max_drawdown DECIMAL(5,4),
    forward_trades INTEGER,
    forward_start_date DATE,

    -- Status
    status VARCHAR(50) DEFAULT 'CANDIDATE',
    -- CANDIDATE: Backtest only, pending forward test
    -- VALIDATED: Passed forward test (6+ months, 100+ signals)
    -- DEPLOYED: Active in live trading
    -- RETIRED: No longer generating signals

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_impl_spec ON strategy_implementations(spec_id);
CREATE INDEX idx_impl_symbol ON strategy_implementations(symbol);
CREATE INDEX idx_impl_status ON strategy_implementations(status);
CREATE INDEX idx_impl_forward_sharpe ON strategy_implementations(forward_sharpe DESC NULLS LAST);

-- GIN index for querying implementations by parameter values
CREATE INDEX idx_impl_parameters_gin ON strategy_implementations USING GIN (parameters);

-- Composite index for finding best implementations
CREATE INDEX idx_impl_best ON strategy_implementations(
    symbol,
    status,
    forward_sharpe DESC NULLS LAST
) WHERE status IN ('VALIDATED', 'DEPLOYED');
```

### Supporting Tables

```sql
-- Track implementation signals for outcome tracking
-- Partitioned by signal_timestamp for scalability at billions of rows
CREATE TABLE implementation_signals (
    signal_id UUID DEFAULT gen_random_uuid(),
    impl_id UUID NOT NULL REFERENCES strategy_implementations(impl_id),
    symbol VARCHAR(50) NOT NULL,
    action VARCHAR(10) NOT NULL,     -- BUY, SELL, HOLD
    entry_price DECIMAL(20,8),
    exit_price DECIMAL(20,8),
    return_pct DECIMAL(8,4),
    signal_timestamp TIMESTAMP NOT NULL,
    exit_timestamp TIMESTAMP,
    signal_type VARCHAR(20) NOT NULL, -- backtest, forward_test, live
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (signal_id, signal_timestamp)
) PARTITION BY RANGE (signal_timestamp);

-- Create partitions by quarter (example for 2025-2026)
CREATE TABLE implementation_signals_2025_q1 PARTITION OF implementation_signals
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
CREATE TABLE implementation_signals_2025_q2 PARTITION OF implementation_signals
    FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE implementation_signals_2025_q3 PARTITION OF implementation_signals
    FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');
CREATE TABLE implementation_signals_2025_q4 PARTITION OF implementation_signals
    FOR VALUES FROM ('2025-10-01') TO ('2026-01-01');
CREATE TABLE implementation_signals_2026_q1 PARTITION OF implementation_signals
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
CREATE TABLE implementation_signals_2026_q2 PARTITION OF implementation_signals
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');

-- Default partition for future data (will auto-route until explicit partition created)
CREATE TABLE implementation_signals_default PARTITION OF implementation_signals DEFAULT;

-- Indexes on partitioned table (created on parent, applied to all partitions)
CREATE INDEX idx_signals_impl ON implementation_signals(impl_id);
CREATE INDEX idx_signals_timestamp ON implementation_signals(signal_timestamp DESC);
CREATE INDEX idx_signals_symbol_timestamp ON implementation_signals(symbol, signal_timestamp DESC);

-- Spec performance aggregates (materialized view)
CREATE MATERIALIZED VIEW spec_performance AS
SELECT
    s.spec_id,
    s.name,
    COUNT(DISTINCT i.impl_id) as implementations_count,
    COUNT(DISTINCT i.impl_id) FILTER (WHERE i.status = 'VALIDATED') as validated_count,
    AVG(i.forward_sharpe) FILTER (WHERE i.status = 'VALIDATED') as avg_forward_sharpe,
    AVG(i.forward_accuracy) FILTER (WHERE i.status = 'VALIDATED') as avg_forward_accuracy,
    MAX(i.forward_sharpe) FILTER (WHERE i.status = 'VALIDATED') as best_forward_sharpe
FROM strategy_specs s
LEFT JOIN strategy_implementations i ON s.spec_id = i.spec_id
GROUP BY s.spec_id, s.name;

CREATE UNIQUE INDEX idx_spec_perf_id ON spec_performance(spec_id);
```

### Partition Management

```sql
-- Function to create new quarterly partitions automatically
CREATE OR REPLACE FUNCTION create_signals_partition(partition_date DATE)
RETURNS void AS $$
DECLARE
    partition_name TEXT;
    start_date DATE;
    end_date DATE;
BEGIN
    -- Calculate quarter boundaries
    start_date := date_trunc('quarter', partition_date);
    end_date := start_date + INTERVAL '3 months';
    partition_name := 'implementation_signals_' ||
                      to_char(start_date, 'YYYY') || '_q' ||
                      EXTRACT(QUARTER FROM start_date);

    -- Create partition if it doesn't exist
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF implementation_signals
         FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date
    );
END;
$$ LANGUAGE plpgsql;

-- Schedule this to run monthly via pg_cron or external scheduler
-- SELECT create_signals_partition(NOW() + INTERVAL '3 months');
```

## Data Archival Policy

### Retention Rules

| Data Type               | Hot Storage | Warm Storage | Archive | Delete        |
| ----------------------- | ----------- | ------------ | ------- | ------------- |
| Live signals            | 6 months    | 2 years      | 5 years | Never         |
| Forward test signals    | 1 year      | 3 years      | 5 years | After 7 years |
| Backtest signals        | 3 months    | 1 year       | 3 years | After 5 years |
| Retired implementations | 6 months    | 2 years      | 5 years | After 7 years |

### Archival Process

```sql
-- Move old backtest signals to archive (run quarterly)
-- Step 1: Create archive table structure (one-time)
CREATE TABLE implementation_signals_archive (
    LIKE implementation_signals INCLUDING ALL
) PARTITION BY RANGE (signal_timestamp);

-- Step 2: Detach old partitions and attach to archive
-- Example: Archive Q1 2025 backtest signals
ALTER TABLE implementation_signals DETACH PARTITION implementation_signals_2025_q1;

-- Filter to keep only backtest signals for archive
INSERT INTO implementation_signals_archive
SELECT * FROM implementation_signals_2025_q1
WHERE signal_type = 'backtest';

-- Re-attach with only non-backtest signals (or drop if empty)
TRUNCATE implementation_signals_2025_q1;
INSERT INTO implementation_signals_2025_q1
SELECT * FROM implementation_signals_2025_q1_backup
WHERE signal_type != 'backtest';

ALTER TABLE implementation_signals ATTACH PARTITION implementation_signals_2025_q1
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
```

### Automated Archival Function

```python
async def archive_old_signals(db, archive_before: datetime):
    """
    Archive signals older than the specified date.
    Run monthly via scheduled job.
    """
    # Get partitions to archive
    partitions = await db.fetch("""
        SELECT relname FROM pg_class
        WHERE relname LIKE 'implementation_signals_%'
          AND relkind = 'r'
          AND relname NOT LIKE '%archive%'
          AND relname NOT LIKE '%default%'
    """)

    for partition in partitions:
        # Extract date range from partition name
        # Archive if entirely before cutoff
        partition_end = extract_partition_end_date(partition["relname"])

        if partition_end < archive_before:
            print(f"Archiving partition: {partition['relname']}")
            await archive_partition(db, partition["relname"])
```

## Data Types

### Indicator Definition

```json
{
  "id": "rsi",
  "type": "RSI",
  "input": "close",
  "params": {
    "period": "${rsiPeriod}"
  }
}
```

### Entry/Exit Condition

```json
{
  "type": "CROSSED_UP",
  "indicator": "rsi",
  "params": {
    "crosses": "rsiEma"
  }
}
```

### Parameter Definition

```json
{
  "name": "rsiPeriod",
  "type": "INTEGER",
  "min": 7,
  "max": 21,
  "defaultValue": 14
}
```

## Seeding from YAML

### Seed Script

```python
# scripts/seed_specs_from_yaml.py

import yaml
import json
import os
from pathlib import Path
from typing import Optional, List

def parse_strategy_yaml(yaml_path: Path) -> dict:
    """Parse a strategy YAML file into spec format."""
    with open(yaml_path) as f:
        config = yaml.safe_load(f)

    return {
        "name": config.get("name") or yaml_path.stem,
        "description": config.get("description"),
        "indicators": parse_indicators(config.get("indicators", [])),
        "entry_conditions": parse_conditions(config.get("entryConditions", [])),
        "exit_conditions": parse_conditions(config.get("exitConditions", [])),
        "parameters": parse_parameters(config.get("parameters", [])),
        "source": "CANONICAL",
        "source_file": str(yaml_path)
    }

def parse_indicators(indicators: list) -> list:
    """Convert YAML indicators to spec format."""
    result = []
    for ind in indicators:
        result.append({
            "id": ind.get("id"),
            "type": ind.get("type"),
            "input": ind.get("input"),
            "params": ind.get("params", {})
        })
    return result

def parse_conditions(conditions: list) -> list:
    """Convert YAML conditions to spec format."""
    result = []
    for cond in conditions:
        result.append({
            "type": cond.get("type"),
            "indicator": cond.get("indicator"),
            "params": cond.get("params", {})
        })
    return result

def parse_parameters(params: List[dict]) -> list:
    """
    Convert YAML parameters to spec format.
    Note: YAML parameters is a list of dicts, not a dict.
    Each param has: name, type, min, max, defaultValue
    """
    result = []
    for param in params:
        result.append({
            "name": param.get("name"),
            "type": param.get("type", "DECIMAL"),
            "min": param.get("min"),
            "max": param.get("max"),
            "defaultValue": param.get("defaultValue"),
            "description": param.get("description")
        })
    return result

async def seed_specs_from_yaml(yaml_dir: str, db):
    """Seed strategy specs from YAML files."""
    yaml_path = Path(yaml_dir)
    yaml_files = list(yaml_path.glob("**/*.yaml")) + list(yaml_path.glob("**/*.yml"))

    print(f"Found {len(yaml_files)} YAML files")

    for yaml_file in yaml_files:
        try:
            spec = parse_strategy_yaml(yaml_file)

            # Check if spec already exists
            existing = await db.fetchrow(
                "SELECT spec_id FROM strategy_specs WHERE name = $1",
                spec["name"]
            )

            if existing:
                print(f"Skipping existing spec: {spec['name']}")
                continue

            # Insert spec
            await db.execute("""
                INSERT INTO strategy_specs
                (name, description, indicators, entry_conditions, exit_conditions,
                 parameters, source, source_file)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                spec["name"],
                spec["description"],
                json.dumps(spec["indicators"]),
                json.dumps(spec["entry_conditions"]),
                json.dumps(spec["exit_conditions"]),
                json.dumps(spec["parameters"]),
                spec["source"],
                spec["source_file"]
            )

            print(f"Created spec: {spec['name']}")

        except Exception as e:
            print(f"Error processing {yaml_file}: {e}")

if __name__ == "__main__":
    import asyncio
    import asyncpg

    async def main():
        db = await asyncpg.connect(os.environ["DATABASE_URL"])
        await seed_specs_from_yaml("src/main/resources/strategies", db)
        await db.close()

    asyncio.run(main())
```

## Migration Procedures

### Migration Scripts

```sql
-- V7__strategy_specs.sql
-- Creates the strategy_specs table and indexes

BEGIN;

CREATE TABLE strategy_specs (
    -- ... (full schema as defined above)
);

-- Create all indexes
CREATE INDEX idx_specs_source ON strategy_specs(source);
CREATE INDEX idx_specs_active ON strategy_specs(is_active);
CREATE INDEX idx_specs_indicators_gin ON strategy_specs USING GIN (indicators);
CREATE INDEX idx_specs_entry_conditions_gin ON strategy_specs USING GIN (entry_conditions);
CREATE INDEX idx_specs_exit_conditions_gin ON strategy_specs USING GIN (exit_conditions);
CREATE INDEX idx_specs_parameters_gin ON strategy_specs USING GIN (parameters);

COMMIT;
```

```sql
-- V8__strategy_implementations.sql
-- Creates the implementations and signals tables

BEGIN;

CREATE TABLE strategy_implementations (
    -- ... (full schema as defined above)
);

-- Create implementations indexes
CREATE INDEX idx_impl_spec ON strategy_implementations(spec_id);
CREATE INDEX idx_impl_symbol ON strategy_implementations(symbol);
CREATE INDEX idx_impl_status ON strategy_implementations(status);
CREATE INDEX idx_impl_forward_sharpe ON strategy_implementations(forward_sharpe DESC NULLS LAST);
CREATE INDEX idx_impl_parameters_gin ON strategy_implementations USING GIN (parameters);
CREATE INDEX idx_impl_best ON strategy_implementations(symbol, status, forward_sharpe DESC NULLS LAST)
    WHERE status IN ('VALIDATED', 'DEPLOYED');

-- Create partitioned signals table
CREATE TABLE implementation_signals (
    -- ... (full schema as defined above)
) PARTITION BY RANGE (signal_timestamp);

-- Create initial partitions
CREATE TABLE implementation_signals_2025_q1 PARTITION OF implementation_signals
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
-- ... additional partitions

CREATE TABLE implementation_signals_default PARTITION OF implementation_signals DEFAULT;

-- Create signals indexes
CREATE INDEX idx_signals_impl ON implementation_signals(impl_id);
CREATE INDEX idx_signals_timestamp ON implementation_signals(signal_timestamp DESC);
CREATE INDEX idx_signals_symbol_timestamp ON implementation_signals(symbol, signal_timestamp DESC);

-- Create materialized view
CREATE MATERIALIZED VIEW spec_performance AS
SELECT
    s.spec_id,
    s.name,
    COUNT(DISTINCT i.impl_id) as implementations_count,
    COUNT(DISTINCT i.impl_id) FILTER (WHERE i.status = 'VALIDATED') as validated_count,
    AVG(i.forward_sharpe) FILTER (WHERE i.status = 'VALIDATED') as avg_forward_sharpe,
    AVG(i.forward_accuracy) FILTER (WHERE i.status = 'VALIDATED') as avg_forward_accuracy,
    MAX(i.forward_sharpe) FILTER (WHERE i.status = 'VALIDATED') as best_forward_sharpe
FROM strategy_specs s
LEFT JOIN strategy_implementations i ON s.spec_id = i.spec_id
GROUP BY s.spec_id, s.name;

CREATE UNIQUE INDEX idx_spec_perf_id ON spec_performance(spec_id);

COMMIT;
```

### Rollback Procedures

```sql
-- R7__strategy_specs_rollback.sql
-- Rollback for V7__strategy_specs.sql

BEGIN;

-- Drop indexes first
DROP INDEX IF EXISTS idx_specs_parameters_gin;
DROP INDEX IF EXISTS idx_specs_exit_conditions_gin;
DROP INDEX IF EXISTS idx_specs_entry_conditions_gin;
DROP INDEX IF EXISTS idx_specs_indicators_gin;
DROP INDEX IF EXISTS idx_specs_active;
DROP INDEX IF EXISTS idx_specs_source;

-- Drop table (CASCADE will handle any dependent objects)
DROP TABLE IF EXISTS strategy_specs CASCADE;

COMMIT;
```

```sql
-- R8__strategy_implementations_rollback.sql
-- Rollback for V8__strategy_implementations.sql

BEGIN;

-- Drop materialized view first
DROP MATERIALIZED VIEW IF EXISTS spec_performance;

-- Drop signals table (includes all partitions)
DROP TABLE IF EXISTS implementation_signals CASCADE;

-- Drop implementations table
DROP INDEX IF EXISTS idx_impl_best;
DROP INDEX IF EXISTS idx_impl_parameters_gin;
DROP INDEX IF EXISTS idx_impl_forward_sharpe;
DROP INDEX IF EXISTS idx_impl_status;
DROP INDEX IF EXISTS idx_impl_symbol;
DROP INDEX IF EXISTS idx_impl_spec;
DROP TABLE IF EXISTS strategy_implementations CASCADE;

COMMIT;
```

### Safe Migration Workflow

```bash
#!/bin/bash
# scripts/migrate.sh

set -e

# 1. Create backup before migration
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Run migration in transaction
psql $DATABASE_URL -f migrations/V7__strategy_specs.sql

# 3. Verify migration succeeded
psql $DATABASE_URL -c "SELECT COUNT(*) FROM strategy_specs;"

# 4. If verification fails, rollback
# psql $DATABASE_URL -f migrations/R7__strategy_specs_rollback.sql
```

## Linking Existing Implementations

```python
async def link_existing_implementations(db):
    """
    Link existing 40M+ implementations to their specs.
    Run after seeding specs.
    """
    # Get all specs
    specs = await db.fetch("SELECT spec_id, name FROM strategy_specs")
    spec_map = {s["name"]: s["spec_id"] for s in specs}

    # Update implementations to reference specs
    # (Assumes existing implementations have strategy_name field)
    for name, spec_id in spec_map.items():
        result = await db.execute("""
            UPDATE strategy_implementations
            SET spec_id = $1
            WHERE strategy_name = $2 AND spec_id IS NULL
        """, spec_id, name)

        print(f"Linked {result} implementations to {name}")
```

## Status Lifecycle

```
                  GA Discovery
                       |
                       v
    +--------------------------------------+
    |            CANDIDATE                  |
    |  * Backtest metrics only              |
    |  * Not yet forward-tested             |
    |  * High overfitting risk              |
    +--------------------------------------+
                       |
                       | 6+ months forward test
                       | 100+ signals
                       | Sharpe > 0.5
                       v
    +--------------------------------------+
    |            VALIDATED                  |
    |  * Forward-test metrics available     |
    |  * Paper trading proven               |
    |  * Ready for live consideration       |
    +--------------------------------------+
                       |
                       | Live trading approved
                       v
    +--------------------------------------+
    |            DEPLOYED                   |
    |  * Active in live trading             |
    |  * Real capital at risk               |
    |  * Highest confidence level           |
    +--------------------------------------+
                       |
                       | Underperformance
                       | (Janitor Agent)
                       v
    +--------------------------------------+
    |            RETIRED                    |
    |  * No longer generating signals       |
    |  * Historical data preserved          |
    |  * May be reactivated if conditions   |
    |    change                             |
    +--------------------------------------+
```

### Status Transition Functions

```python
async def validate_implementation(impl_id: str, db) -> bool:
    """
    Check if implementation meets validation criteria and update status.
    """
    impl = await db.fetchrow("""
        SELECT forward_trades, forward_sharpe, forward_start_date
        FROM strategy_implementations
        WHERE impl_id = $1
    """, impl_id)

    if not impl:
        return False

    # Validation criteria
    months_active = (datetime.now() - impl["forward_start_date"]).days / 30
    meets_criteria = (
        impl["forward_trades"] >= 100 and
        months_active >= 6 and
        impl["forward_sharpe"] >= 0.5
    )

    if meets_criteria:
        await db.execute("""
            UPDATE strategy_implementations
            SET status = 'VALIDATED', updated_at = NOW()
            WHERE impl_id = $1
        """, impl_id)
        return True

    return False

async def retire_implementation(
    impl_id: str,
    reason: str,
    db
) -> bool:
    """
    Retire an implementation.
    """
    await db.execute("""
        UPDATE strategy_implementations
        SET status = 'RETIRED',
            updated_at = NOW()
        WHERE impl_id = $1
    """, impl_id)

    # Also update spec if all implementations retired
    spec_id = await db.fetchval("""
        SELECT spec_id FROM strategy_implementations WHERE impl_id = $1
    """, impl_id)

    active_impls = await db.fetchval("""
        SELECT COUNT(*) FROM strategy_implementations
        WHERE spec_id = $1 AND status != 'RETIRED'
    """, spec_id)

    if active_impls == 0:
        # Check if CANONICAL - never retire original specs
        is_canonical = await db.fetchval("""
            SELECT source = 'CANONICAL' FROM strategy_specs WHERE spec_id = $1
        """, spec_id)

        if not is_canonical:
            await db.execute("""
                UPDATE strategy_specs
                SET is_active = FALSE,
                    retired_at = NOW(),
                    retired_reason = $2
                WHERE spec_id = $1
            """, spec_id, reason)

    return True
```

## Queries

### Get Top Implementations for Symbol

```sql
SELECT
    i.impl_id,
    s.name as spec_name,
    i.parameters,
    i.forward_sharpe,
    i.forward_accuracy,
    i.forward_trades,
    i.status
FROM strategy_implementations i
JOIN strategy_specs s ON i.spec_id = s.spec_id
WHERE i.symbol = $1
  AND i.status IN ('VALIDATED', 'DEPLOYED')
ORDER BY i.forward_sharpe DESC
LIMIT $2;
```

### Get Top Specs for Learning Agent

```sql
SELECT
    s.spec_id,
    s.name,
    s.indicators,
    s.entry_conditions,
    s.exit_conditions,
    s.parameters,
    sp.avg_forward_sharpe,
    sp.validated_count
FROM strategy_specs s
JOIN spec_performance sp ON s.spec_id = sp.spec_id
WHERE s.is_active = TRUE
  AND sp.validated_count >= 5
ORDER BY sp.avg_forward_sharpe DESC
LIMIT $1;
```

### Query Signals by Time Range (Leverages Partitioning)

```sql
-- This query benefits from partition pruning
SELECT
    s.impl_id,
    COUNT(*) as signal_count,
    AVG(s.return_pct) as avg_return,
    SUM(CASE WHEN s.return_pct > 0 THEN 1 ELSE 0 END)::float / COUNT(*) as win_rate
FROM implementation_signals s
WHERE s.signal_timestamp >= '2025-06-01'
  AND s.signal_timestamp < '2025-09-01'
  AND s.signal_type = 'forward_test'
GROUP BY s.impl_id
ORDER BY avg_return DESC;
```

## Acceptance Criteria

- [ ] All 70+ YAML configs seeded as specs with source='CANONICAL'
- [ ] Existing 40M+ implementations linked to specs
- [ ] Forward test metrics tracked separately from backtest
- [ ] Status lifecycle enforced (CANDIDATE -> VALIDATED -> DEPLOYED -> RETIRED)
- [ ] CANONICAL specs protected from retirement
- [ ] spec_performance materialized view refreshes correctly
- [ ] Migration scripts run without errors
- [ ] Seed script idempotent (safe to run multiple times)
- [ ] GIN indexes created for JSONB columns
- [ ] implementation_signals table partitioned by timestamp
- [ ] Rollback scripts tested and documented
- [ ] Data archival policy documented and scheduled

## File Structure

```
db/
├── migrations/
│   ├── V7__strategy_specs.sql
│   ├── V8__strategy_implementations.sql
│   ├── R7__strategy_specs_rollback.sql
│   └── R8__strategy_implementations_rollback.sql
└── seeds/
    └── seed_specs_from_yaml.py

services/strategy_db/
├── __init__.py
├── models.py
├── repository.py
├── lifecycle.py
├── archival.py
└── tests/
    └── test_lifecycle.py
```
