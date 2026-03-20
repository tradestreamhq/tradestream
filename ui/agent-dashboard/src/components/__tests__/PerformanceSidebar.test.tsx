import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PerformanceSidebar } from "../PerformanceSidebar";
import { createMockSignal } from "./testHelpers";

describe("PerformanceSidebar", () => {
  it("renders with empty signals", () => {
    render(<PerformanceSidebar signals={[]} />);
    expect(screen.getByLabelText("Strategy performance")).toBeDefined();
    expect(screen.getByText("N/A")).toBeDefined(); // Win rate with no data
    expect(screen.getByText("0 BUY · 0 SELL · 0 HOLD")).toBeDefined();
  });

  it("counts BUY/SELL/HOLD signals", () => {
    const signals = [
      createMockSignal({ signal_id: "s1", action: "BUY" }),
      createMockSignal({ signal_id: "s2", action: "BUY" }),
      createMockSignal({ signal_id: "s3", action: "SELL" }),
      createMockSignal({ signal_id: "s4", action: "HOLD" }),
    ];
    render(<PerformanceSidebar signals={signals} />);
    expect(screen.getByText(/2 BUY/)).toBeDefined();
    expect(screen.getByText(/1 SELL/)).toBeDefined();
    expect(screen.getByText(/1 HOLD/)).toBeDefined();
  });

  it("calculates open positions", () => {
    const signals = [
      createMockSignal({ signal_id: "s1", action: "BUY", entry_price: undefined, current_price: undefined }),
      createMockSignal({ signal_id: "s2", action: "SELL", entry_price: undefined, current_price: undefined }),
    ];
    render(<PerformanceSidebar signals={signals} />);
    // Open positions = 2 (1 buy + 1 sell without prices)
    expect(screen.getByText("1 buys")).toBeDefined();
    expect(screen.getByText("1 sells")).toBeDefined();
  });

  it("shows win/loss stats for resolved signals", () => {
    const signals = [
      createMockSignal({ signal_id: "s1", action: "BUY", entry_price: 100, current_price: 110 }), // win
      createMockSignal({ signal_id: "s2", action: "BUY", entry_price: 100, current_price: 90 }),  // loss
      createMockSignal({ signal_id: "s3", action: "BUY", entry_price: 100, current_price: 120 }), // win
    ];
    render(<PerformanceSidebar signals={signals} />);
    expect(screen.getByText("2W / 1L of 3 resolved")).toBeDefined();
  });

  it("has accessible landmark role", () => {
    render(<PerformanceSidebar signals={[]} />);
    const sidebar = screen.getByLabelText("Strategy performance");
    expect(sidebar.tagName).toBe("ASIDE");
  });
});
