# Database Migrations

This directory contains database migrations for TradeStream, managed by **Alembic**.

## Directory Structure

```
database/
├── migrations/           # Legacy Flyway SQL files (V1-V9, kept for reference)
├── alembic/              # Alembic migration framework (primary)
│   ├── alembic.ini       # Alembic configuration
│   ├── env.py            # Migration environment setup
│   ├── run_migrations.py # Standalone migration runner
│   ├── Dockerfile        # Container image for Kubernetes deployment
│   ├── script.py.mako    # Migration template
│   └── versions/         # Versioned migrations
│       └── _001_baseline_schema.py
└── README.md
```

## Current Schema

| Migration | Tables |
|-----------|--------|
| 001 (V1-V9) | `Strategies`, `strategy_specs`, `strategy_implementations`, `strategy_performance`, `signals`, `walk_forward_results`, `agent_decisions`, `paper_trades`, `paper_portfolio` |

## Running Migrations

### Alembic (Python)

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

### Kubernetes (Helm)

Migrations run automatically as a Helm hook during `helm install` or `helm upgrade`:

```bash
helm upgrade --install tradestream ./charts/tradestream
```

The migration container runs Alembic's `upgrade head` before other workloads start. For databases previously managed by Flyway, set `databaseMigration.stampOnly: true` on the first deployment.

## Adding New Migrations

1. Create an Alembic migration: `alembic revision -m "description"` in `database/alembic/`
2. Implement `upgrade()` and `downgrade()` functions
3. Run tests: `bazel test //database/alembic:alembic_test`
4. Test locally before deploying

## Important: No Inline DDL

**Application code must NOT create or modify database tables.** All schema changes must go through the Alembic migration framework. Services should only verify that expected tables exist at startup (read-only check).

## Configuration

Migration configuration is in `charts/tradestream/values.yaml`:

```yaml
databaseMigration:
  enabled: true
  stampOnly: false  # Set to true for databases already managed by Flyway
```

## Rollback

Alembic supports downgrade:

```bash
# Downgrade one revision
alembic -c database/alembic/alembic.ini downgrade -1

# Check current revision
alembic -c database/alembic/alembic.ini current
```

## Troubleshooting

### Migration job fails

```bash
kubectl logs job/tradestream-db-migration -n tradestream
```

### Schema already exists

For existing databases, use `--stamp-only` to mark migrations as applied without executing them:

```bash
python -m database.alembic.run_migrations --stamp-only
```
