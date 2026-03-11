import React from "react";
import type { AgentEvent } from "../types";
import { SignalCard } from "./SignalCard";

interface SignalStreamProps {
  events: AgentEvent[];
  title?: string;
}

export function SignalStream({ events, title = "Signal Stream" }: SignalStreamProps) {
  return (
    <div className="section" role="feed" aria-label={title}>
      <div className="section-header">
        <span>{title}</span>
        <span className="badge">{events.length}</span>
      </div>
      <div className="signal-list">
        {events.length === 0 ? (
          <div className="empty-state">No events yet. Waiting for agent activity...</div>
        ) : (
          events.map((event) => <SignalCard key={event.id} event={event} />)
        )}
      </div>
    </div>
  );
}
