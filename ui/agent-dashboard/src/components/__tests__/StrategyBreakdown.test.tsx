import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";
import { StrategyBreakdown } from "../StrategyBreakdown";
import { createMockSignal } from "./testHelpers";

describe("StrategyBreakdown", () => {
  const strategies = createMockSignal().strategy_breakdown;

  it("renders strategy names", () => {
    render(<StrategyBreakdown strategies={strategies} />);
    expect(screen.getByText("RSI_REVERSAL")).toBeInTheDocument();
    expect(screen.getByText("MACD_CROSS")).toBeInTheDocument();
    expect(screen.getByText("VOLUME_BREAKOUT")).toBeInTheDocument();
  });

  it("shows agreement icons", () => {
    render(<StrategyBreakdown strategies={strategies} />);
    const agreeIcons = screen.getAllByText("\u2713");
    const disagreeIcons = screen.getAllByText("\u2717");
    expect(agreeIcons).toHaveLength(2);
    expect(disagreeIcons).toHaveLength(1);
  });

  it("returns null for empty strategies", () => {
    const { container } = render(<StrategyBreakdown strategies={[]} />);
    expect(container.innerHTML).toBe("");
  });
});
