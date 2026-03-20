import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { StrategyBreakdown } from "../StrategyBreakdown";

const mockStrategies = [
  { strategy_name: "RSI_REVERSAL", action: "BUY" as const, score: 0.89, reason: "RSI oversold recovery" },
  { strategy_name: "MACD_CROSS", action: "BUY" as const, score: 0.85, reason: "Bullish crossover" },
  { strategy_name: "VOLUME_BREAKOUT", action: "SELL" as const, score: 0.65, reason: "Volume declining" },
];

describe("StrategyBreakdown", () => {
  it("renders all strategies", () => {
    render(<StrategyBreakdown strategies={mockStrategies} />);

    expect(screen.getByText("RSI_REVERSAL")).toBeInTheDocument();
    expect(screen.getByText("MACD_CROSS")).toBeInTheDocument();
    expect(screen.getByText("VOLUME_BREAKOUT")).toBeInTheDocument();
  });

  it("shows scores formatted", () => {
    render(<StrategyBreakdown strategies={mockStrategies} />);

    expect(screen.getByText("0.89")).toBeInTheDocument();
    expect(screen.getByText("0.85")).toBeInTheDocument();
    expect(screen.getByText("0.65")).toBeInTheDocument();
  });

  it("shows reasons", () => {
    render(<StrategyBreakdown strategies={mockStrategies} />);

    expect(screen.getByText("RSI oversold recovery")).toBeInTheDocument();
    expect(screen.getByText("Volume declining")).toBeInTheDocument();
  });

  it("returns null for empty strategies", () => {
    const { container } = render(<StrategyBreakdown strategies={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("has section heading", () => {
    render(<StrategyBreakdown strategies={mockStrategies} />);
    expect(screen.getByText("Strategy Breakdown")).toBeInTheDocument();
  });
});
