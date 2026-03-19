import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SignalHistoryPage } from "../SignalHistoryPage";
import type { Signal } from "@/api/types";

vi.mock("@/api/client", () => ({
  fetchSignals: vi.fn(),
}));

import { fetchSignals } from "@/api/client";

const mockSignals: Signal[] = [
  {
    signal_id: "sig1",
    symbol: "BTC/USD",
    action: "BUY",
    confidence: 0.85,
    opportunity_score: 0.9,
    opportunity_tier: "HOT",
    entry_price: 65000,
    stop_loss: 63000,
    take_profit: 70000,
    strategies_analyzed: 10,
    strategies_bullish: 7,
    strategies_bearish: 3,
    reasoning: "Strong momentum",
    outcome: "WIN",
    pnl_percent: 0.075,
    timestamp: "2026-03-18T12:00:00Z",
  },
  {
    signal_id: "sig2",
    symbol: "ETH/USD",
    action: "SELL",
    confidence: 0.6,
    opportunity_score: 0.5,
    opportunity_tier: "NEUTRAL",
    entry_price: 3500,
    stop_loss: 3700,
    take_profit: 3200,
    strategies_analyzed: 8,
    strategies_bullish: 2,
    strategies_bearish: 6,
    reasoning: "Bearish divergence",
    outcome: "LOSS",
    pnl_percent: -0.04,
    timestamp: "2026-03-17T08:30:00Z",
  },
  {
    signal_id: "sig3",
    symbol: "SOL/USD",
    action: "BUY",
    confidence: 0.7,
    opportunity_score: 0.65,
    opportunity_tier: "GOOD",
    entry_price: 150,
    stop_loss: 140,
    take_profit: 170,
    strategies_analyzed: 5,
    strategies_bullish: 4,
    strategies_bearish: 1,
    reasoning: "Breakout pattern",
    outcome: "PENDING",
    timestamp: "2026-03-19T10:00:00Z",
  },
];

describe("SignalHistoryPage", () => {
  it("renders heading and filter controls", async () => {
    vi.mocked(fetchSignals).mockResolvedValue(mockSignals);
    render(<SignalHistoryPage />);

    expect(screen.getByText("Signal History")).toBeInTheDocument();
    expect(screen.getByLabelText("Symbol")).toBeInTheDocument();
    expect(screen.getByLabelText("Action")).toBeInTheDocument();
    expect(screen.getByLabelText("Outcome")).toBeInTheDocument();
  });

  it("shows summary statistics labels", async () => {
    vi.mocked(fetchSignals).mockResolvedValue(mockSignals);
    render(<SignalHistoryPage />);

    await waitFor(() => {
      // Stats section has labels as .text-xs.text-slate-400 divs
      expect(screen.getAllByText("Total").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Wins").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Losses").length).toBeGreaterThan(0);
    });
  });

  it("shows empty state when no signals match", async () => {
    vi.mocked(fetchSignals).mockResolvedValue([]);
    render(<SignalHistoryPage />);

    await waitFor(() => {
      expect(
        screen.getByText("No signals found matching your filters.")
      ).toBeInTheDocument();
    });
  });

  it("shows error state on fetch failure", async () => {
    vi.mocked(fetchSignals).mockRejectedValue(new Error("Server error"));
    render(<SignalHistoryPage />);

    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
  });
});
