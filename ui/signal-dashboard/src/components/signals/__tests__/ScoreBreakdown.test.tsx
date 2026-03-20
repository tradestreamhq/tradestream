import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ScoreBreakdown } from "../ScoreBreakdown";
import type { OpportunityFactors } from "@/api/types";

const mockFactors: OpportunityFactors = {
  confidence: { value: 0.82, contribution: 20.5 },
  expected_return: { value: 0.032, contribution: 30.0 },
  consensus: { value: 0.8, contribution: 16.0 },
  volatility: { value: 0.021, contribution: 10.5 },
  freshness: { value: 2, contribution: 10.0 },
};

describe("ScoreBreakdown", () => {
  it("renders all five factor rows", () => {
    render(<ScoreBreakdown factors={mockFactors} totalScore={87} />);

    expect(screen.getByText("Confidence")).toBeInTheDocument();
    expect(screen.getByText("Expected Return")).toBeInTheDocument();
    expect(screen.getByText("Strategy Consensus")).toBeInTheDocument();
    expect(screen.getByText("Volatility")).toBeInTheDocument();
    expect(screen.getByText("Freshness")).toBeInTheDocument();
  });

  it("renders formatted values", () => {
    render(<ScoreBreakdown factors={mockFactors} totalScore={87} />);

    expect(screen.getByText("82%")).toBeInTheDocument();
    expect(screen.getByText("+3.2%")).toBeInTheDocument();
    expect(screen.getByText("80%")).toBeInTheDocument();
    expect(screen.getByText("2.1%")).toBeInTheDocument();
    expect(screen.getByText("2m ago")).toBeInTheDocument();
  });

  it("renders contribution points", () => {
    render(<ScoreBreakdown factors={mockFactors} totalScore={87} />);

    expect(screen.getByText("+20.5 pts")).toBeInTheDocument();
    expect(screen.getByText("+30.0 pts")).toBeInTheDocument();
    expect(screen.getByText("+16.0 pts")).toBeInTheDocument();
    expect(screen.getByText("+10.5 pts")).toBeInTheDocument();
    expect(screen.getByText("+10.0 pts")).toBeInTheDocument();
  });

  it("renders total score", () => {
    render(<ScoreBreakdown factors={mockFactors} totalScore={87} />);
    expect(screen.getByText("Total: 87.0 pts")).toBeInTheDocument();
  });

  it("has proper accessibility attributes", () => {
    render(<ScoreBreakdown factors={mockFactors} totalScore={87} />);
    expect(screen.getByText("Score Breakdown")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Score factors" })).toBeInTheDocument();
  });
});
