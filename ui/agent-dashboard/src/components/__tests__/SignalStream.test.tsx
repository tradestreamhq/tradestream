import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";
import { SignalStream } from "../SignalStream";
import { createMockEvent } from "./testHelpers";

// Mock react-window to avoid measuring issues in JSDOM
vi.mock("react-window", () => ({
  VariableSizeList: ({ children: Row, itemCount }: any) => (
    <div data-testid="virtual-list">
      {Array.from({ length: Math.min(itemCount, 10) }, (_, i) => (
        <Row key={i} index={i} style={{}} />
      ))}
    </div>
  ),
}));

describe("SignalStream", () => {
  it("shows empty state when no events", () => {
    render(<SignalStream events={[]} />);
    expect(screen.getByText(/No signals match/)).toBeInTheDocument();
  });

  it("renders filter bar with action buttons", () => {
    render(<SignalStream events={[]} />);
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("SELL")).toBeInTheDocument();
    expect(screen.getByText("HOLD")).toBeInTheDocument();
  });

  it("renders signal cards from events", () => {
    const events = [
      createMockEvent({ id: "1", signal_id: "s1", score: 0.9 }),
      createMockEvent({ id: "2", signal_id: "s2", score: 0.7, event_type: "reasoning" }),
    ];
    render(<SignalStream events={events} />);
    // Only signal events become cards
    expect(screen.getByText("90")).toBeInTheDocument();
  });

  it("renders P&L tracker sidebar", () => {
    render(<SignalStream events={[]} />);
    expect(screen.getByText("Live P&L")).toBeInTheDocument();
  });

  it("has accessible list role", () => {
    render(<SignalStream events={[]} />);
    expect(screen.getByRole("list", { name: /Trading signals/ })).toBeInTheDocument();
  });

  it("renders min score filter", () => {
    render(<SignalStream events={[]} />);
    expect(screen.getByLabelText("Min score:")).toBeInTheDocument();
  });

  it("renders with custom title", () => {
    render(<SignalStream events={[]} title="My Signals" />);
    expect(screen.getByText("My Signals")).toBeInTheDocument();
  });

  it("shows signal count in live region", () => {
    render(<SignalStream events={[]} />);
    expect(screen.getByRole("status")).toHaveTextContent("0 signals available");
  });
});
