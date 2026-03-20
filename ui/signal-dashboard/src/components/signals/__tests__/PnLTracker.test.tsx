import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PnLTracker } from "../PnLTracker";
import type { Signal } from "@/api/types";

function makeSignal(overrides: Partial<Signal> = {}): Signal {
  return {
    signal_id: "sig-1",
    symbol: "BTC/USD",
    action: "BUY",
    confidence: 0.85,
    opportunity_score: 87,
    opportunity_tier: "HOT",
    entry_price: 42000,
    stop_loss: 41000,
    take_profit: 44000,
    strategies_analyzed: 5,
    strategies_bullish: 4,
    strategies_bearish: 1,
    reasoning: "Strong signal.",
    timestamp: "2026-03-19T10:30:00Z",
    ...overrides,
  };
}

describe("PnLTracker", () => {
  it("shows zero P&L with no signals", () => {
    render(<PnLTracker signals={[]} />);
    expect(screen.getByText("+0.00%")).toBeInTheDocument();
    expect(screen.getByText("0 open")).toBeInTheDocument();
  });

  it("sums realized P&L from closed signals", () => {
    const signals = [
      makeSignal({ signal_id: "s1", outcome: "WIN", pnl_percent: 0.032 }),
      makeSignal({ signal_id: "s2", outcome: "LOSS", pnl_percent: -0.01 }),
    ];

    render(<PnLTracker signals={signals} />);
    // 3.2% - 1.0% = 2.2%
    expect(screen.getByText("+2.20%")).toBeInTheDocument();
  });

  it("counts open positions", () => {
    const signals = [
      makeSignal({ signal_id: "s1" }),
      makeSignal({ signal_id: "s2", outcome: "PENDING" }),
      makeSignal({ signal_id: "s3", outcome: "WIN", pnl_percent: 0.01 }),
    ];

    render(<PnLTracker signals={signals} />);
    expect(screen.getByText("2 open")).toBeInTheDocument();
  });

  it("has correct aria-label", () => {
    render(<PnLTracker signals={[]} />);
    expect(screen.getByLabelText("P&L tracker")).toBeInTheDocument();
  });
});
