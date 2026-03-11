import React, { useState } from "react";
import type { AgentEvent } from "../types";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { ToolCallLog } from "./ToolCallLog";

interface SignalCardProps {
  event: AgentEvent;
}

function formatTime(isoString: string): string {
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return isoString;
  }
}

export function SignalCard({ event }: SignalCardProps) {
  const [expanded, setExpanded] = useState(false);

  const tierClass = event.tier === "high" ? "high" : event.tier === "medium" ? "medium" : "low";

  return (
    <div
      className="signal-card"
      onClick={() => setExpanded(!expanded)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          setExpanded(!expanded);
        }
      }}
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
      aria-label={`${event.event_type} from ${event.agent_name ?? "unknown"}`}
    >
      <div className="signal-card-header">
        <span className="signal-agent">{event.agent_name ?? "unknown"}</span>
        <span className="signal-time">{formatTime(event.created_at)}</span>
      </div>

      <div className="signal-content">
        {event.tier && <span className={`tier-badge ${tierClass}`}>{event.tier}</span>}
        {event.score != null && (
          <span className="signal-score">{(event.score * 100).toFixed(1)}%</span>
        )}
        <span className="tier-badge" style={{ background: "rgba(139,92,246,0.15)", color: "#8b5cf6" }}>
          {event.event_type}
        </span>
      </div>

      {event.reasoning && <div className="signal-reasoning">{event.reasoning}</div>}

      {expanded && (
        <div className="signal-details">
          <div className="signal-meta">
            {event.model_used && <span>Model: {event.model_used}</span>}
            {event.latency_ms != null && <span>Latency: {event.latency_ms}ms</span>}
            {event.tokens_used != null && <span>Tokens: {event.tokens_used}</span>}
            {event.success != null && (
              <span style={{ color: event.success ? "var(--accent-green)" : "var(--accent-red)" }}>
                {event.success ? "Success" : "Failed"}
              </span>
            )}
          </div>
          {event.error_message && (
            <div style={{ marginTop: 8, color: "var(--accent-red)", fontSize: 12 }}>
              {event.error_message}
            </div>
          )}
          {event.score != null && <ScoreBreakdown score={event.score} tier={event.tier} />}
          {event.tool_calls && <ToolCallLog toolCalls={event.tool_calls} />}
        </div>
      )}
    </div>
  );
}
