import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";
import type { AgentEvent } from "../../types";
import { SignalCard } from "../SignalCard";

const mockEvent: AgentEvent = {
  event_type: "signal",
  id: "test-123",
  signal_id: "sig-456",
  agent_name: "signal-generator",
  decision_type: null,
  score: 0.85,
  tier: "high",
  reasoning: "Strong momentum detected in BTC",
  tool_calls: null,
  model_used: "claude-3",
  latency_ms: 150,
  tokens_used: 500,
  success: true,
  error_message: null,
  created_at: "2026-03-11T10:30:00Z",
};

describe("SignalCard", () => {
  it("renders agent name and score", () => {
    render(<SignalCard event={mockEvent} />);
    expect(screen.getByText("signal-generator")).toBeInTheDocument();
    expect(screen.getByText("85.0%")).toBeInTheDocument();
  });

  it("renders tier badge", () => {
    render(<SignalCard event={mockEvent} />);
    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("renders reasoning text", () => {
    render(<SignalCard event={mockEvent} />);
    expect(screen.getByText("Strong momentum detected in BTC")).toBeInTheDocument();
  });

  it("expands on click to show details", () => {
    render(<SignalCard event={mockEvent} />);
    const card = screen.getByRole("button");
    expect(card).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(card);
    expect(card).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Model: claude-3")).toBeInTheDocument();
    expect(screen.getByText("Latency: 150ms")).toBeInTheDocument();
  });

  it("collapses on second click", () => {
    render(<SignalCard event={mockEvent} />);
    const card = screen.getByRole("button");
    fireEvent.click(card);
    expect(card).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(card);
    expect(card).toHaveAttribute("aria-expanded", "false");
  });

  it("expands on Enter key", () => {
    render(<SignalCard event={mockEvent} />);
    const card = screen.getByRole("button");
    fireEvent.keyDown(card, { key: "Enter" });
    expect(card).toHaveAttribute("aria-expanded", "true");
  });
});
