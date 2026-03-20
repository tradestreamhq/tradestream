import React from "react";
import type { AgentEvent } from "../types";

interface ToolCallLogProps {
  events: AgentEvent[];
}

export function ToolCallLog({ events }: ToolCallLogProps) {
  const toolEvents = events.filter((e) => e.event_type === "tool_call" && e.tool_calls);
  if (!toolEvents.length) return null;

  return (
    <div className="tool-call-list" aria-label="Tool call log">
      <div className="tool-call-header">Tool Calls</div>
      {toolEvents.map((event) =>
        event.tool_calls?.map((tc, i) => (
          <div className="tool-call-item" key={`${event.id}-${i}`}>
            <span className="tool-badge">[tool]</span>
            <span className="tool-name">{tc.name}</span>
            {tc.args && (
              <span className="tool-args">
                ({Object.entries(tc.args).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})
              </span>
            )}
            {tc.latency_ms != null && (
              <span className="tool-latency">{tc.latency_ms}ms</span>
            )}
            {tc.result != null && (
              <div className="tool-result">
                {"\u2192"} {typeof tc.result === "string" ? tc.result : JSON.stringify(tc.result).slice(0, 120)}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
