import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SignalCard } from "../SignalCard";
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
    reasoning: "Strong bullish consensus across strategies.",
    timestamp: "2026-03-19T10:30:00Z",
    ...overrides,
  };
}

describe("SignalCard", () => {
  it("renders signal basic info", () => {
    render(<SignalCard signal={makeSignal()} />);

    expect(screen.getByText("BTC/USD")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("HOT")).toBeInTheDocument();
    expect(screen.getByText("85.0%")).toBeInTheDocument();
    expect(screen.getByText("42,000.00")).toBeInTheDocument();
  });

  it("renders entry, stop loss, take profit", () => {
    render(<SignalCard signal={makeSignal()} />);

    expect(screen.getByText("41,000.00")).toBeInTheDocument();
    expect(screen.getByText("44,000.00")).toBeInTheDocument();
  });

  it("shows expand toggle and reasoning on expand", () => {
    const onToggle = vi.fn();
    const { rerender } = render(
      <SignalCard signal={makeSignal()} expanded={false} onToggle={onToggle} />
    );

    const btn = screen.getByText("Show details");
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(onToggle).toHaveBeenCalled();

    rerender(
      <SignalCard signal={makeSignal()} expanded={true} onToggle={onToggle} />
    );
    expect(
      screen.getByText("Strong bullish consensus across strategies.")
    ).toBeInTheDocument();
    expect(screen.getByText("Hide details")).toBeInTheDocument();
  });

  it("displays SELL badge correctly", () => {
    render(<SignalCard signal={makeSignal({ action: "SELL" })} />);
    expect(screen.getByText("SELL")).toBeInTheDocument();
  });

  it("shows outcome and pnl when present", () => {
    render(
      <SignalCard
        signal={makeSignal({
          outcome: "WIN",
          pnl_percent: 0.032,
        })}
        expanded={true}
        onToggle={() => {}}
      />
    );

    expect(screen.getByText("WIN")).toBeInTheDocument();
    expect(screen.getByText("+3.20%")).toBeInTheDocument();
  });

  it("has correct aria-label on article", () => {
    render(<SignalCard signal={makeSignal()} />);
    expect(
      screen.getByLabelText("BUY signal for BTC/USD")
    ).toBeInTheDocument();
  });
});
