-- V5.3__agent_decisions_partitions.sql
-- Optional partitioning setup for large-scale deployments.
-- This creates a function to auto-create monthly partitions.

-- Function to create monthly partitions automatically
CREATE OR REPLACE FUNCTION create_monthly_partition(
    table_name TEXT,
    partition_date DATE
) RETURNS VOID AS $$
DECLARE
    partition_name TEXT;
    start_date DATE;
    end_date DATE;
BEGIN
    start_date := date_trunc('month', partition_date);
    end_date := start_date + INTERVAL '1 month';
    partition_name := table_name || '_' || to_char(start_date, 'YYYY_MM');

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I
         FOR VALUES FROM (%L) TO (%L)',
        partition_name, table_name, start_date, end_date
    );
END;
$$ LANGUAGE plpgsql;

-- Create partitions for current and next month
-- (Run via cron or application startup)
-- SELECT create_monthly_partition('agent_decisions', CURRENT_DATE);
-- SELECT create_monthly_partition('agent_decisions', CURRENT_DATE + INTERVAL '1 month');
