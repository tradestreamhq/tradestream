import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SignalCard } from "../SignalCard";
import type { Signal, OpportunityFactors } from "@/api/types";

const mockFactors: OpportunityFactors = {
  confidence: { value: 0.82, contribution: 20.5 },
  expected_return: { value: 0.032, contribution: 30.0 },
  consensus: { value: 0.8, contribution: 16.0 },
  volatility: { value: 0.021, contribution: 10.5 },
  freshness: { value: 2, contribution: 10.0 },
};

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
  it("renders signal basic info with opportunity score", () => {
    render(<SignalCard signal={makeSignal()} />);

    expect(screen.getByText("BTC/USD")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("HOT")).toBeInTheDocument();
    expect(screen.getByText("87")).toBeInTheDocument();
  });

  it("renders entry, stop loss, take profit", () => {
    render(<SignalCard signal={makeSignal()} />);

    expect(screen.getByText("41,000.00")).toBeInTheDocument();
    expect(screen.getByText("44,000.00")).toBeInTheDocument();
  });

  it("shows strategies ratio", () => {
    render(<SignalCard signal={makeSignal()} />);
    expect(screen.getByText("4/5 bullish")).toBeInTheDocument();
  });

  it("shows expand toggle and reasoning on expand", () => {
    const onToggle = vi.fn();
    const { rerender } = render(
      <SignalCard signal={makeSignal()} expanded={false} onToggle={onToggle} />
    );

    const btn = screen.getByText(/Show reasoning/);
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(onToggle).toHaveBeenCalled();

    rerender(
      <SignalCard signal={makeSignal()} expanded={true} onToggle={onToggle} />
    );
    expect(
      screen.getByText("Strong bullish consensus across strategies.")
    ).toBeInTheDocument();
    expect(screen.getByText(/Hide reasoning/)).toBeInTheDocument();
  });

  it("displays SELL badge correctly", () => {
    render(<SignalCard signal={makeSignal({ action: "SELL" })} />);
    expect(screen.getByText("SELL")).toBeInTheDocument();
  });

  it("applies correct border color for BUY signals", () => {
    const { container } = render(<SignalCard signal={makeSignal({ action: "BUY" })} />);
    const article = container.querySelector("article");
    expect(article?.className).toContain("border-l-emerald-500");
  });

  it("applies correct border color for SELL signals", () => {
    const { container } = render(<SignalCard signal={makeSignal({ action: "SELL" })} />);
    const article = container.querySelector("article");
    expect(article?.className).toContain("border-l-red-500");
  });

  it("applies correct border color for HOLD signals", () => {
    const { container } = render(<SignalCard signal={makeSignal({ action: "HOLD" })} />);
    const article = container.querySelector("article");
    expect(article?.className).toContain("border-l-amber-500");
  });

  it("shows outcome and pnl when present", () => {
    render(
      <SignalCard
        signal={makeSignal({ outcome: "WIN", pnl_percent: 0.032 })}
        expanded={true}
        onToggle={() => {}}
      />
    );

    expect(screen.getByText("WIN")).toBeInTheDocument();
    expect(screen.getByText("+3.20%")).toBeInTheDocument();
  });

  it("renders score breakdown when opportunity_factors present", () => {
    render(
      <SignalCard
        signal={makeSignal({ opportunity_factors: mockFactors })}
        expanded={true}
        onToggle={() => {}}
      />
    );

    expect(screen.getByText("Score Breakdown")).toBeInTheDocument();
    expect(screen.getByText("Confidence")).toBeInTheDocument();
    expect(screen.getByText("Expected Return")).toBeInTheDocument();
    expect(screen.getByText("+20.5 pts")).toBeInTheDocument();
  });

  it("renders strategy breakdown when present", () => {
    render(
      <SignalCard
        signal={makeSignal({
          strategy_breakdown: [
            { strategy_name: "RSI_REVERSAL", action: "BUY", score: 0.89, reason: "RSI oversold" },
            { strategy_name: "MACD_CROSS", action: "SELL", score: 0.65, reason: "Bearish cross" },
          ],
        })}
        expanded={true}
        onToggle={() => {}}
      />
    );

    expect(screen.getByText("Strategy Breakdown")).toBeInTheDocument();
    expect(screen.getByText("RSI_REVERSAL")).toBeInTheDocument();
    expect(screen.getByText("MACD_CROSS")).toBeInTheDocument();
  });

  it("has correct aria-label with opportunity score", () => {
    render(<SignalCard signal={makeSignal()} />);
    expect(
      screen.getByLabelText("BUY signal for BTC/USD with opportunity score 87")
    ).toBeInTheDocument();
  });

  it("applies focused ring when isFocused", () => {
    const { container } = render(
      <SignalCard signal={makeSignal()} isFocused={true} />
    );
    const article = container.querySelector("article");
    expect(article?.className).toContain("ring-2");
  });

  it("renders tool call log when events provided", () => {
    render(
      <SignalCard
        signal={makeSignal()}
        expanded={true}
        onToggle={() => {}}
        toolEvents={[
          { event_type: "tool_call", tool_name: "get_top_strategies", arguments: 'symbol="ETH/USD"', latency_ms: 45 },
        ]}
      />
    );

    expect(screen.getByText("Tool Calls")).toBeInTheDocument();
    expect(screen.getByText(/get_top_strategies/)).toBeInTheDocument();
    expect(screen.getByText("45ms")).toBeInTheDocument();
  });
});
