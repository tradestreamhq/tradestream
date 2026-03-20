-- V5.1__agent_decisions_gin.sql
-- GIN indexes for JSONB queries (tool call analysis, strategy filtering).

CREATE INDEX IF NOT EXISTS idx_agent_decisions_tool_calls_gin
    ON agent_decisions USING GIN (tool_calls jsonb_path_ops);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_strategy_breakdown_gin
    ON agent_decisions USING GIN (strategy_breakdown jsonb_path_ops);
