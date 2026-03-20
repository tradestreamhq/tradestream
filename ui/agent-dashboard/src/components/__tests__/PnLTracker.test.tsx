import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";
import { PnLTracker } from "../PnLTracker";
import { createMockSignal } from "./testHelpers";

describe("PnLTracker", () => {
  it("renders Live P&L header", () => {
    render(<PnLTracker signals={[]} />);
    expect(screen.getByText("Live P&L")).toBeInTheDocument();
  });

  it("shows 0% when no signals have prices", () => {
    render(<PnLTracker signals={[createMockSignal()]} />);
    expect(screen.getByText("+0.00%")).toBeInTheDocument();
  });

  it("calculates positive P&L for BUY signals", () => {
    const signal = createMockSignal({
      entry_price: 100,
      current_price: 105,
      action: "BUY",
    });
    render(<PnLTracker signals={[signal]} />);
    const pnlValues = screen.getAllByText("+5.00%");
    expect(pnlValues.length).toBeGreaterThanOrEqual(1);
  });

  it("calculates positive P&L for SELL signals", () => {
    const signal = createMockSignal({
      entry_price: 100,
      current_price: 95,
      action: "SELL",
    });
    render(<PnLTracker signals={[signal]} />);
    const pnlValues = screen.getAllByText("+5.00%");
    expect(pnlValues.length).toBeGreaterThanOrEqual(1);
  });

  it("shows win rate", () => {
    render(<PnLTracker signals={[]} />);
    expect(screen.getByText("Win Rate")).toBeInTheDocument();
  });
});
