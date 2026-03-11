import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";
import type { AgentEvent } from "../../types";
import { SignalStream } from "../SignalStream";

const mockEvents: AgentEvent[] = [
  {
    event_type: "signal",
    id: "1",
    signal_id: "s1",
    agent_name: "signal-generator",
    decision_type: null,
    score: 0.9,
    tier: "high",
    reasoning: "Bullish",
    tool_calls: null,
    model_used: null,
    latency_ms: null,
    tokens_used: null,
    success: true,
    error_message: null,
    created_at: "2026-03-11T10:00:00Z",
  },
  {
    event_type: "reasoning",
    id: "2",
    signal_id: null,
    agent_name: "scorer",
    decision_type: "analysis",
    score: null,
    tier: null,
    reasoning: "Analyzing market",
    tool_calls: null,
    model_used: null,
    latency_ms: null,
    tokens_used: null,
    success: true,
    error_message: null,
    created_at: "2026-03-11T09:55:00Z",
  },
];

describe("SignalStream", () => {
  it("renders events", () => {
    render(<SignalStream events={mockEvents} />);
    expect(screen.getByText("signal-generator")).toBeInTheDocument();
    expect(screen.getByText("scorer")).toBeInTheDocument();
  });

  it("shows event count badge", () => {
    render(<SignalStream events={mockEvents} />);
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("shows empty state when no events", () => {
    render(<SignalStream events={[]} />);
    expect(screen.getByText(/No events yet/)).toBeInTheDocument();
  });

  it("renders with custom title", () => {
    render(<SignalStream events={[]} title="Custom Stream" />);
    expect(screen.getByText("Custom Stream")).toBeInTheDocument();
  });

  it("has feed role for accessibility", () => {
    render(<SignalStream events={[]} />);
    expect(screen.getByRole("feed")).toBeInTheDocument();
  });
});
