import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { StrategyLeaderboardPage } from "../StrategyLeaderboardPage";
import type { Strategy } from "@/api/types";

vi.mock("@/api/client", () => ({
  fetchStrategies: vi.fn(),
}));

import { fetchStrategies } from "@/api/client";

const mockStrategies: Strategy[] = [
  {
    strategy_id: "s1",
    name: "Mean Reversion",
    description: "Buys dips",
    win_rate: 0.72,
    total_signals: 150,
    sharpe_ratio: 1.8,
    total_return: 0.35,
    max_drawdown: -0.12,
    avg_return_per_trade: 0.023,
    active: true,
  },
  {
    strategy_id: "s2",
    name: "Momentum Alpha",
    description: "Rides trends",
    win_rate: 0.65,
    total_signals: 200,
    sharpe_ratio: 2.1,
    total_return: -0.05,
    max_drawdown: -0.2,
    avg_return_per_trade: -0.002,
    active: false,
  },
];

describe("StrategyLeaderboardPage", () => {
  it("renders loading state", () => {
    vi.mocked(fetchStrategies).mockReturnValue(new Promise(() => {}));
    render(<StrategyLeaderboardPage />);
    expect(screen.getByText("Strategy Leaderboard")).toBeInTheDocument();
  });

  it("renders strategies after loading", async () => {
    vi.mocked(fetchStrategies).mockResolvedValue(mockStrategies);
    render(<StrategyLeaderboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Mean Reversion").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Momentum Alpha").length).toBeGreaterThan(0);
    });
  });

  it("shows error state on fetch failure", async () => {
    vi.mocked(fetchStrategies).mockRejectedValue(new Error("Network error"));
    render(<StrategyLeaderboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("shows active/inactive badges", async () => {
    vi.mocked(fetchStrategies).mockResolvedValue(mockStrategies);
    render(<StrategyLeaderboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Inactive").length).toBeGreaterThan(0);
    });
  });
});
