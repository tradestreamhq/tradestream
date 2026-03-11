import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";
import type { ActiveAgent } from "../../types";
import { AgentPanel } from "../AgentPanel";

const mockAgents: ActiveAgent[] = [
  {
    agent_name: "signal-generator",
    decision_count: 10,
    last_active: "2026-03-11T12:00:00Z",
    avg_latency_ms: 120,
    success_count: 9,
    failure_count: 1,
  },
  {
    agent_name: "opportunity-scorer",
    decision_count: 5,
    last_active: "2026-03-11T11:58:00Z",
    avg_latency_ms: 80,
    success_count: 5,
    failure_count: 0,
  },
];

describe("AgentPanel", () => {
  it("renders agent names", () => {
    render(<AgentPanel agents={mockAgents} />);
    expect(screen.getByText("signal-generator")).toBeInTheDocument();
    expect(screen.getByText("opportunity-scorer")).toBeInTheDocument();
  });

  it("shows agent count badge", () => {
    render(<AgentPanel agents={mockAgents} />);
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("shows empty state", () => {
    render(<AgentPanel agents={[]} />);
    expect(screen.getByText(/No active agents/)).toBeInTheDocument();
  });

  it("renders stats for each agent", () => {
    render(<AgentPanel agents={mockAgents} />);
    expect(screen.getByText("10 decisions")).toBeInTheDocument();
    expect(screen.getByText("9 ok")).toBeInTheDocument();
    expect(screen.getByText("1 err")).toBeInTheDocument();
  });
});
