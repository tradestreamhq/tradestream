import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";
import { ScoreBreakdown } from "../ScoreBreakdown";
import { createMockSignal } from "./testHelpers";

describe("ScoreBreakdown", () => {
  const signal = createMockSignal();

  it("renders all five factors", () => {
    render(<ScoreBreakdown factors={signal.opportunity_factors} totalScore={87} />);
    expect(screen.getByText("Confidence")).toBeInTheDocument();
    expect(screen.getByText("Expected Return")).toBeInTheDocument();
    expect(screen.getByText("Strategy Consensus")).toBeInTheDocument();
    expect(screen.getByText("Volatility")).toBeInTheDocument();
    expect(screen.getByText("Freshness")).toBeInTheDocument();
  });

  it("renders total score", () => {
    render(<ScoreBreakdown factors={signal.opportunity_factors} totalScore={87} />);
    expect(screen.getByText("Total: 87.0 pts")).toBeInTheDocument();
  });

  it("renders progress bars for each factor", () => {
    render(<ScoreBreakdown factors={signal.opportunity_factors} totalScore={87} />);
    const progressBars = screen.getAllByRole("progressbar");
    expect(progressBars).toHaveLength(5);
  });

  it("displays contribution points", () => {
    render(<ScoreBreakdown factors={signal.opportunity_factors} totalScore={87} />);
    expect(screen.getByText("+20.5 pts")).toBeInTheDocument();
    expect(screen.getByText("+30.0 pts")).toBeInTheDocument();
  });
});
