# Database Migrations

This directory contains database migrations for TradeStream.

## Migration Tools

TradeStream uses two complementary migration frameworks:

- **Flyway** (Java/Kubernetes): Runs as a Helm hook during deployment. SQL files in `migrations/`.
- **Alembic** (Python): Manages schema for Python services. Configuration in `alembic/`.

Both frameworks track the same schema. The Alembic baseline migration (`001`) consolidates all Flyway V1-V9 migrations and uses `IF NOT EXISTS` so it's a no-op on existing databases.

## Directory Structure

```
database/
├── migrations/           # Flyway SQL migration files (V1-V9)
├── alembic/              # Alembic migration framework
│   ├── alembic.ini       # Alembic configuration
│   ├── env.py            # Migration environment setup
│   ├── run_migrations.py # Standalone migration runner
│   ├── script.py.mako    # Migration template
│   └── versions/         # Versioned migrations
│       └── 001_baseline_schema.py
└── README.md
```

## Current Schema

| Migration | Tables |
|-----------|--------|
| V1 / 001 | `Strategies` |
| V2 / 001 | `strategy_specs`, `strategy_implementations` |
| V3 / 001 | `strategy_performance` |
| V4 / 001 | `signals` |
| V5 / 001 | Walk-forward columns on `Strategies`, `walk_forward_results` |
| V6 / 001 | `agent_decisions` |
| V7 / 001 | Enhanced `agent_decisions` columns |
| V8 / 001 | `paper_trades` |
| V9 / 001 | `paper_portfolio` |

## Running Migrations

### Alembic (Python services)

```bash
# Set environment variables
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=tradestream
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=your_password

# Run all pending migrations
python -m database.alembic.run_migrations

# For existing databases (already managed by Flyway), stamp without running:
python -m database.alembic.run_migrations --stamp-only
```

### Flyway (Kubernetes)

Migrations run automatically as a Helm hook during `helm install` or `helm upgrade`:

```bash
helm upgrade --install tradestream ./charts/tradestream
```

### Locally with Flyway

```bash
docker run --rm \
  -v $(pwd)/database/migrations:/flyway/sql \
  flyway/flyway:10.22-alpine \
  -url=jdbc:postgresql://localhost:5432/tradestream \
  -user=postgres \
  -password=your_password \
  migrate
```

## Adding New Migrations

For new schema changes, add migrations to **both** frameworks:

1. Create a Flyway migration: `database/migrations/V10__description.sql`
2. Create an Alembic migration: `alembic revision -m "description"` in `database/alembic/`
3. Update the Helm ConfigMap: `charts/tradestream/templates/database-migration-configmap.yaml`
4. Test locally before deploying

## Important: No Inline DDL

**Application code must NOT create or modify database tables.** All schema changes must go through the migration framework. Services should only verify that expected tables exist at startup (read-only check).

## Configuration

Migration configuration is in `charts/tradestream/values.yaml`:

```yaml
databaseMigration:
  enabled: true
  baselineOnMigrate: "true"  # Creates baseline for existing databases
  baselineVersion: "0"       # Version to use as baseline
  connectRetries: 60         # Retries before failing
```

## Rollback

Flyway Community Edition does not support automatic rollback. For production rollbacks:

1. Create a new migration that reverses the changes
2. Example: `V10__rollback_v9_paper_portfolio.sql`

## Troubleshooting

### Migration job fails

```bash
kubectl logs job/tradestream-db-migration -n tradestream
```

### Alembic current revision

```bash
alembic -c database/alembic/alembic.ini current
```

### Schema already exists

For existing databases, use `alembic stamp head` or `--stamp-only` to mark migrations as applied without executing them.
