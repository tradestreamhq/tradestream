import React from "react";
import { AgentPanel } from "./components/AgentPanel";
import { SignalStream } from "./components/SignalStream";
import { StatCard } from "./components/StatCard";
import { useAgentStream } from "./hooks/useAgentStream";
import { useDashboard } from "./hooks/useDashboard";

export default function App() {
  const { summary, signals, loading, error, refresh } = useDashboard();
  const { events: liveEvents, status } = useAgentStream();

  // Merge live SSE events with polled signals, deduplicating by id
  const allEvents = React.useMemo(() => {
    const seen = new Set<string>();
    const merged = [];
    for (const ev of [...liveEvents, ...signals]) {
      if (ev.id && !seen.has(ev.id)) {
        seen.add(ev.id);
        merged.push(ev);
      }
    }
    return merged;
  }, [liveEvents, signals]);

  if (loading && !summary) {
    return <div className="loading">Loading dashboard...</div>;
  }

  const stats = summary?.stats_24h;

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Agent Command Center</h1>
        <div className="connection-status">
          <div className={`status-dot ${status}`} />
          <span>{status === "connected" ? "Live" : status === "connecting" ? "Connecting..." : "Disconnected"}</span>
        </div>
      </div>

      {error && (
        <div className="error-banner" role="alert">
          <span>{error}</span>
          <button onClick={refresh}>Retry</button>
        </div>
      )}

      {stats && (
        <div className="stats-grid">
          <StatCard label="Decisions (24h)" value={stats.total_decisions} color="blue" />
          <StatCard label="Active Agents" value={stats.unique_agents} color="green" />
          <StatCard label="Signals" value={stats.signals_generated} color="yellow" />
          <StatCard label="Success Rate" value={stats.total_decisions > 0 ? `${((stats.successes / stats.total_decisions) * 100).toFixed(1)}%` : "N/A"} color="green" />
          <StatCard label="Avg Latency" value={stats.avg_latency_ms ? `${Math.round(stats.avg_latency_ms)}ms` : "N/A"} />
          <StatCard label="Failures" value={stats.failures} color="red" />
        </div>
      )}

      <div className="main-content">
        <SignalStream events={allEvents} title="Live Signal Stream" />
        <div>
          <AgentPanel agents={summary?.active_agents ?? []} />
          {summary?.tier_distribution && Object.keys(summary.tier_distribution).length > 0 && (
            <div className="section" style={{ marginTop: 16 }}>
              <div className="section-header">Tier Distribution (24h)</div>
              <div style={{ padding: 16 }}>
                {Object.entries(summary.tier_distribution).map(([tier, count]) => (
                  <div className="score-factor" key={tier}>
                    <span className="factor-label">{tier}</span>
                    <div className="score-bar-container">
                      <div
                        className="score-bar"
                        style={{
                          width: `${(count / Math.max(...Object.values(summary.tier_distribution))) * 100}%`,
                          background: tier === "high" ? "var(--tier-hot)" : tier === "medium" ? "var(--tier-good)" : "var(--tier-neutral)",
                        }}
                      />
                    </div>
                    <span className="score-value">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
