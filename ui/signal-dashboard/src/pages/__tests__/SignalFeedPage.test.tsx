import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { SignalFeedPage } from "../SignalFeedPage";
import type { Signal } from "@/api/types";

const mockReconnect = vi.fn();
const mockUseSignalStream = vi.fn();

vi.mock("@/hooks/useSignalStream", () => ({
  useSignalStream: (...args: unknown[]) => mockUseSignalStream(...args),
}));

const mockSignals: Signal[] = [
  {
    signal_id: "s1",
    symbol: "BTC/USD",
    action: "BUY",
    confidence: 0.9,
    opportunity_score: 0.85,
    opportunity_tier: "HOT",
    entry_price: 65000,
    stop_loss: 63000,
    take_profit: 70000,
    strategies_analyzed: 10,
    strategies_bullish: 8,
    strategies_bearish: 2,
    reasoning: "Strong uptrend",
    timestamp: "2026-03-19T10:00:00Z",
  },
  {
    signal_id: "s2",
    symbol: "ETH/USD",
    action: "SELL",
    confidence: 0.7,
    opportunity_score: 0.6,
    opportunity_tier: "GOOD",
    entry_price: 3500,
    stop_loss: 3700,
    take_profit: 3200,
    strategies_analyzed: 8,
    strategies_bullish: 2,
    strategies_bearish: 6,
    reasoning: "Bearish divergence",
    timestamp: "2026-03-19T09:30:00Z",
  },
];

beforeEach(() => {
  mockUseSignalStream.mockReturnValue({
    signals: mockSignals,
    isConnected: true,
    reconnect: mockReconnect,
  });
});

describe("SignalFeedPage", () => {
  it("renders heading and live status", () => {
    render(<SignalFeedPage />);
    expect(screen.getByText("Live Signal Feed")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("renders signal cards", () => {
    render(<SignalFeedPage />);
    expect(screen.getByText("BTC/USD")).toBeInTheDocument();
    expect(screen.getByText("ETH/USD")).toBeInTheDocument();
  });

  it("filters signals by action using filter buttons", () => {
    render(<SignalFeedPage />);

    // Click SELL filter - use getAllByRole to find filter buttons specifically
    const filterButtons = screen.getAllByRole("button");
    const sellButton = filterButtons.find(
      (btn) => btn.textContent === "SELL"
    )!;
    fireEvent.click(sellButton);

    expect(screen.queryByText("BTC/USD")).not.toBeInTheDocument();
    expect(screen.getByText("ETH/USD")).toBeInTheDocument();
  });

  it("shows waiting message when no signals", () => {
    mockUseSignalStream.mockReturnValue({
      signals: [],
      isConnected: true,
      reconnect: mockReconnect,
    });
    render(<SignalFeedPage />);
    expect(screen.getByText("Waiting for signals...")).toBeInTheDocument();
  });

  it("shows disconnected state and reconnect button", () => {
    mockUseSignalStream.mockReturnValue({
      signals: [],
      isConnected: false,
      reconnect: mockReconnect,
    });
    render(<SignalFeedPage />);
    expect(screen.getByText("Disconnected")).toBeInTheDocument();
    expect(screen.getByText("Reconnect")).toBeInTheDocument();
  });

  it("has a feed region with aria-label", () => {
    render(<SignalFeedPage />);
    expect(screen.getByRole("feed")).toHaveAttribute(
      "aria-label",
      "Trading signals sorted by opportunity score"
    );
  });
});
