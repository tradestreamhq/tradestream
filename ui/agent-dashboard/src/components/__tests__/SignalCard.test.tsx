import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";
import { SignalCard } from "../SignalCard";
import { createMockSignal } from "./testHelpers";

describe("SignalCard", () => {
  const defaultProps = {
    signal: createMockSignal(),
    isExpanded: false,
    onToggleExpand: vi.fn(),
  };

  it("renders signal action and symbol", () => {
    render(<SignalCard {...defaultProps} />);
    expect(screen.getByText(/BUY/)).toBeInTheDocument();
    expect(screen.getByText("ETH/USD")).toBeInTheDocument();
  });

  it("renders opportunity score", () => {
    render(<SignalCard {...defaultProps} />);
    expect(screen.getByText("87")).toBeInTheDocument();
  });

  it("renders confidence percentage", () => {
    render(<SignalCard {...defaultProps} />);
    expect(screen.getByText(/Confidence:/)).toBeInTheDocument();
  });

  it("shows correct action class for BUY", () => {
    render(<SignalCard {...defaultProps} />);
    const article = screen.getByRole("article");
    const actionEl = article.querySelector(".action-buy");
    expect(actionEl).toBeTruthy();
  });

  it("shows correct action class for SELL", () => {
    const signal = createMockSignal({ action: "SELL" });
    render(<SignalCard {...defaultProps} signal={signal} />);
    const article = screen.getByRole("article");
    const actionEl = article.querySelector(".action-sell");
    expect(actionEl).toBeTruthy();
  });

  it("calls onToggleExpand when expand button clicked", () => {
    const onToggleExpand = vi.fn();
    render(<SignalCard {...defaultProps} onToggleExpand={onToggleExpand} />);
    fireEvent.click(screen.getByText(/Show reasoning/));
    expect(onToggleExpand).toHaveBeenCalledOnce();
  });

  it("shows detailed content when expanded", () => {
    render(<SignalCard {...defaultProps} isExpanded={true} />);
    expect(screen.getByText("Score Breakdown")).toBeInTheDocument();
    expect(screen.getByText("Analysis")).toBeInTheDocument();
    expect(screen.getByText("Strategy Breakdown")).toBeInTheDocument();
  });

  it("shows hide reasoning text when expanded", () => {
    render(<SignalCard {...defaultProps} isExpanded={true} />);
    expect(screen.getByText(/Hide reasoning/)).toBeInTheDocument();
  });

  it("has proper aria-label", () => {
    render(<SignalCard {...defaultProps} />);
    expect(screen.getByRole("article")).toHaveAttribute(
      "aria-label",
      "BUY signal for ETH/USD with opportunity score 87"
    );
  });

  it("applies focused class when isFocused is true", () => {
    render(<SignalCard {...defaultProps} isFocused={true} />);
    expect(screen.getByRole("article").className).toContain("focused");
  });
});
