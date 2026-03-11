import type { AgentDetail, AgentEvent, DashboardSummary } from "./types";

const BASE_URL = import.meta.env.VITE_API_URL || "/api";

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  return fetchJSON<DashboardSummary>("/dashboard/summary");
}

export async function fetchAgentDetails(
  agentName?: string,
): Promise<{ agents: AgentDetail[] }> {
  const params = agentName ? `?agent_name=${encodeURIComponent(agentName)}` : "";
  return fetchJSON<{ agents: AgentDetail[] }>(`/dashboard/agents${params}`);
}

export async function fetchSignals(
  hours = 24,
  limit = 100,
): Promise<{ signals: AgentEvent[]; count: number; hours: number }> {
  return fetchJSON(`/dashboard/signals?hours=${hours}&limit=${limit}`);
}

export async function fetchRecentEvents(
  limit = 50,
  agentName?: string,
): Promise<{ events: AgentEvent[]; count: number }> {
  let params = `?limit=${limit}`;
  if (agentName) params += `&agent_name=${encodeURIComponent(agentName)}`;
  return fetchJSON(`/events/recent${params}`);
}
