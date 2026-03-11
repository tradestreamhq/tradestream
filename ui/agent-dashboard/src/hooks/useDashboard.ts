import { useCallback, useEffect, useState } from "react";
import { fetchAgentDetails, fetchDashboardSummary, fetchSignals } from "../api";
import type { AgentDetail, AgentEvent, DashboardSummary } from "../types";

const POLL_INTERVAL_MS = 15000;

export function useDashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [agents, setAgents] = useState<AgentDetail[]>([]);
  const [signals, setSignals] = useState<AgentEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [summaryData, agentsData, signalsData] = await Promise.all([
        fetchDashboardSummary(),
        fetchAgentDetails(),
        fetchSignals(24, 100),
      ]);
      setSummary(summaryData);
      setAgents(agentsData.agents);
      setSignals(signalsData.signals);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  return { summary, agents, signals, loading, error, refresh };
}
