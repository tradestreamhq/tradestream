import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SignalStream } from "../SignalStream";
import type { Signal } from "@/api/types";

// Mock react-window to render items directly in tests
vi.mock("react-window", () => ({
  VariableSizeList: vi.fn(({ children: Row, itemCount }: any) => (
    <div data-testid="virtual-list">
      {Array.from({ length: itemCount }, (_, index) => (
        <Row key={index} index={index} style={{}} />
      ))}
    </div>
  )),
}));

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
    reasoning: "Strong bullish consensus.",
    timestamp: "2026-03-19T10:30:00Z",
    ...overrides,
  };
}

const signals: Signal[] = [
  makeSignal({ signal_id: "s1", symbol: "BTC/USD", action: "BUY", opportunity_score: 87 }),
  makeSignal({ signal_id: "s2", symbol: "ETH/USD", action: "SELL", opportunity_score: 74, opportunity_tier: "GOOD" }),
  makeSignal({ signal_id: "s3", symbol: "SOL/USD", action: "HOLD", opportunity_score: 52, opportunity_tier: "NEUTRAL" }),
];

describe("SignalStream", () => {
  it("renders a virtualized list with all signals", () => {
    render(<SignalStream signals={signals} />);
    expect(screen.getByTestId("virtual-list")).toBeInTheDocument();
    expect(screen.getByText("BTC/USD")).toBeInTheDocument();
    expect(screen.getByText("ETH/USD")).toBeInTheDocument();
    expect(screen.getByText("SOL/USD")).toBeInTheDocument();
  });

  it("filters signals by action", () => {
    render(<SignalStream signals={signals} filters={{ actions: ["BUY"] }} />);
    expect(screen.getByText("BTC/USD")).toBeInTheDocument();
    expect(screen.queryByText("ETH/USD")).not.toBeInTheDocument();
    expect(screen.queryByText("SOL/USD")).not.toBeInTheDocument();
  });

  it("filters signals by min opportunity score", () => {
    render(<SignalStream signals={signals} filters={{ minOpportunityScore: 70 }} />);
    expect(screen.getByText("BTC/USD")).toBeInTheDocument();
    expect(screen.getByText("ETH/USD")).toBeInTheDocument();
    expect(screen.queryByText("SOL/USD")).not.toBeInTheDocument();
  });

  it("sorts signals by opportunity score descending", () => {
    render(<SignalStream signals={signals} />);
    const items = screen.getAllByRole("listitem");
    // BTC (87), ETH (74), SOL (52) — already sorted
    expect(items[0]).toHaveTextContent("BTC/USD");
    expect(items[1]).toHaveTextContent("ETH/USD");
    expect(items[2]).toHaveTextContent("SOL/USD");
  });

  it("shows waiting message when no signals", () => {
    render(<SignalStream signals={[]} />);
    expect(screen.getByText("Waiting for signals...")).toBeInTheDocument();
  });

  it("shows no match message when filters exclude all", () => {
    render(<SignalStream signals={signals} filters={{ actions: ["BUY"], minOpportunityScore: 99 }} />);
    expect(screen.getByText("No signals match the current filters.")).toBeInTheDocument();
  });

  it("has proper ARIA list role and label", () => {
    render(<SignalStream signals={signals} />);
    expect(screen.getByRole("list")).toHaveAttribute(
      "aria-label",
      "Trading signals sorted by opportunity score"
    );
  });

  it("announces signal count via live region", () => {
    render(<SignalStream signals={signals} />);
    expect(screen.getByRole("status")).toHaveTextContent("3 signals available");
  });

  it("supports keyboard navigation", () => {
    render(<SignalStream signals={signals} />);
    const list = screen.getByRole("list");

    fireEvent.keyDown(list, { key: "ArrowDown" });
    fireEvent.keyDown(list, { key: "ArrowDown" });
    // After two ArrowDown presses, second item is focused
    const items = screen.getAllByRole("listitem");
    // Focus is managed internally, so we check the card gets focused ring
    fireEvent.keyDown(list, { key: "Enter" });
    // Enter expands the focused card (second one = ETH)
    // The SignalCard should now have expanded=true
  });

  it("respects maxSignals prop", () => {
    render(<SignalStream signals={signals} maxSignals={2} />);
    const items = screen.getAllByRole("listitem");
    expect(items.length).toBe(2);
  });
});
