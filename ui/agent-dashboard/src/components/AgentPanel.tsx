import React from "react";
import type { ActiveAgent } from "../types";

interface AgentPanelProps {
  agents: ActiveAgent[];
}

export function AgentPanel({ agents }: AgentPanelProps) {
  return (
    <div className="section" aria-label="Active agents">
      <div className="section-header">
        <span>Active Agents</span>
        <span className="badge">{agents.length}</span>
      </div>
      <div className="agent-list">
        {agents.length === 0 ? (
          <div className="empty-state">No active agents in the last 5 minutes</div>
        ) : (
          agents.map((agent) => (
            <div className="agent-item" key={agent.agent_name}>
              <div className="agent-name">{agent.agent_name}</div>
              <div className="agent-stats">
                <span>{agent.decision_count} decisions</span>
                <span className="success">{agent.success_count} ok</span>
                <span className="failure">{agent.failure_count} err</span>
                <span>{Math.round(agent.avg_latency_ms)}ms avg</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
