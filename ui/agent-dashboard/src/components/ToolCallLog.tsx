import React from "react";
import type { ToolCall } from "../types";

interface ToolCallLogProps {
  toolCalls: ToolCall[];
}

export function ToolCallLog({ toolCalls }: ToolCallLogProps) {
  if (!toolCalls.length) return null;

  return (
    <div className="tool-call-list" aria-label="Tool call log">
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>
        Tool Calls ({toolCalls.length})
      </div>
      {toolCalls.map((tc, i) => (
        <div className="tool-call-item" key={i}>
          <span className="tool-name">{tc.name}</span>
          {tc.args && (
            <span style={{ color: "var(--text-muted)", marginLeft: 8 }}>
              {JSON.stringify(tc.args).slice(0, 80)}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
