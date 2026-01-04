# Database Migrations

This directory contains Flyway database migrations for TradeStream.

## Migration Tool

TradeStream uses [Flyway](https://flywaydb.org/) for database migrations. Migrations are executed automatically during Helm chart deployment via an init job.

## Directory Structure

```
database/
├── migrations/           # SQL migration files
│   ├── V1__*.sql        # Baseline schema
│   ├── V2__*.sql        # Strategy specs tables
│   ├── V3__*.sql        # Performance tracking
│   └── V4__*.sql        # Signal history
└── README.md            # This file
```

## Naming Convention

Migrations follow Flyway's versioned naming convention:
```
V{version}__{description}.sql
```

Examples:
- `V1__baseline_strategies_table.sql`
- `V2__add_strategy_specs.sql`
- `V3__add_strategy_performance.sql`

## Current Migrations

| Version | Description | Tables Created |
|---------|-------------|----------------|
| V1 | Baseline | `Strategies` |
| V2 | Strategy Specs | `strategy_specs`, `strategy_implementations` |
| V3 | Performance | `strategy_performance` |
| V4 | Signals | `signals` |

## Running Migrations

### In Kubernetes (Production)

Migrations run automatically as a Helm hook during `helm install` or `helm upgrade`:

```bash
helm upgrade --install tradestream ./charts/tradestream
```

The migration job:
1. Waits for PostgreSQL to be ready
2. Runs Flyway with all pending migrations
3. Deletes itself after successful completion

### Locally (Development)

```bash
# Using Docker
docker run --rm \
  -v $(pwd)/database/migrations:/flyway/sql \
  flyway/flyway:10.22-alpine \
  -url=jdbc:postgresql://localhost:5432/tradestream \
  -user=postgres \
  -password=your_password \
  migrate

# Or using Flyway CLI
flyway -url=jdbc:postgresql://localhost:5432/tradestream \
       -user=postgres \
       -password=your_password \
       -locations=filesystem:./database/migrations \
       migrate
```

## Adding New Migrations

1. Create a new file in `database/migrations/`:
   ```
   V5__your_description.sql
   ```

2. Add the migration SQL to the Helm ConfigMap:
   Edit `charts/tradestream/templates/database-migration-configmap.yaml`

3. Test locally before deploying

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
2. Example: `V5__rollback_v4_signals.sql`

## Troubleshooting

### Migration job fails

Check job logs:
```bash
kubectl logs job/tradestream-db-migration -n tradestream
```

### Database connection issues

Verify PostgreSQL is running:
```bash
kubectl get pods -n tradestream | grep postgresql
```

Check connection details:
```bash
kubectl describe job/tradestream-db-migration -n tradestream
```

### Schema already exists

If running on an existing database, Flyway's `baselineOnMigrate` setting will:
1. Create the `flyway_schema_history` table
2. Mark all existing migrations as applied
3. Only run new migrations going forward
