import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PerformanceSidebar } from "../PerformanceSidebar";
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
    timestamp: new Date().toISOString(),
    ...overrides,
  };
}

describe("PerformanceSidebar", () => {
  it("renders all stat sections", () => {
    render(<PerformanceSidebar signals={[]} />);

    expect(screen.getByText("Today's P&L")).toBeInTheDocument();
    expect(screen.getByText("Win Rate")).toBeInTheDocument();
    expect(screen.getByText("Current Streak")).toBeInTheDocument();
    expect(screen.getByText("Open Positions")).toBeInTheDocument();
    expect(screen.getByText("Total Signals")).toBeInTheDocument();
  });

  it("computes win rate from resolved signals", () => {
    const signals = [
      makeSignal({ signal_id: "s1", outcome: "WIN", pnl_percent: 0.02 }),
      makeSignal({ signal_id: "s2", outcome: "WIN", pnl_percent: 0.01 }),
      makeSignal({ signal_id: "s3", outcome: "LOSS", pnl_percent: -0.01 }),
    ];

    render(<PerformanceSidebar signals={signals} />);
    // 2/3 = 66.7%
    expect(screen.getByText("66.7%")).toBeInTheDocument();
    expect(screen.getByText("2W / 1L of 3 resolved")).toBeInTheDocument();
  });

  it("counts open positions by action type", () => {
    const signals = [
      makeSignal({ signal_id: "s1", action: "BUY" }),
      makeSignal({ signal_id: "s2", action: "BUY" }),
      makeSignal({ signal_id: "s3", action: "SELL" }),
      makeSignal({ signal_id: "s4", action: "BUY", outcome: "WIN", pnl_percent: 0.01 }),
    ];

    render(<PerformanceSidebar signals={signals} />);
    expect(screen.getByText("3")).toBeInTheDocument(); // 3 open positions
    expect(screen.getByText("2 buys")).toBeInTheDocument();
    expect(screen.getByText("1 sells")).toBeInTheDocument();
  });

  it("shows signal counts by action", () => {
    const signals = [
      makeSignal({ signal_id: "s1", action: "BUY" }),
      makeSignal({ signal_id: "s2", action: "SELL" }),
      makeSignal({ signal_id: "s3", action: "HOLD" }),
    ];

    render(<PerformanceSidebar signals={signals} />);
    expect(screen.getByText("1 BUY")).toBeInTheDocument();
    expect(screen.getByText("1 SELL")).toBeInTheDocument();
    expect(screen.getByText("1 HOLD")).toBeInTheDocument();
  });

  it("shows N/A win rate when no resolved signals", () => {
    render(<PerformanceSidebar signals={[makeSignal()]} />);
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });
});
