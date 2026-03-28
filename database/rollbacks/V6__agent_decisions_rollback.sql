-- V6__agent_decisions_rollback.sql
-- Rollback: drop agent_decisions table and indexes

DROP INDEX IF EXISTS idx_agent_decisions_signal_id;
DROP INDEX IF EXISTS idx_agent_decisions_created_at;
DROP TABLE IF EXISTS agent_decisions;
