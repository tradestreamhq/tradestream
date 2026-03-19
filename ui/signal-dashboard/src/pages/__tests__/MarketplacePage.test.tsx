import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MarketplacePage } from "../MarketplacePage";

vi.mock("@/api/marketplace", () => ({
  fetchMarketplaceStrategies: vi.fn(),
  fetchLeaderboard: vi.fn(),
  fetchCategories: vi.fn(),
  subscribeToStrategy: vi.fn(),
}));

import {
  fetchMarketplaceStrategies,
  fetchLeaderboard,
  fetchCategories,
} from "@/api/marketplace";

const mockListings = {
  items: [
    {
      id: "l1",
      strategy_id: "s1",
      name: "MACD Crossover",
      author: "alice",
      description: "Momentum strategy using MACD",
      category: "momentum",
      tags: ["crypto", "momentum"],
      performance_stats: { sharpe_ratio: 1.8 },
      price: 0,
      subscribers_count: 42,
      avg_rating: 4.5,
      rating_count: 10,
      created_at: "2026-01-01T00:00:00Z",
    },
  ],
  total: 1,
};

const mockCategories = [
  { name: "momentum", label: "Momentum", description: "Price momentum" },
  { name: "breakout", label: "Breakout", description: "Range breakouts" },
];

describe("MarketplacePage", () => {
  it("renders loading state", () => {
    vi.mocked(fetchMarketplaceStrategies).mockReturnValue(new Promise(() => {}));
    vi.mocked(fetchCategories).mockResolvedValue(mockCategories);
    render(<MarketplacePage />);
    expect(screen.getByText("Strategy Marketplace")).toBeInTheDocument();
  });

  it("renders marketplace listings", async () => {
    vi.mocked(fetchMarketplaceStrategies).mockResolvedValue(mockListings);
    vi.mocked(fetchCategories).mockResolvedValue(mockCategories);
    render(<MarketplacePage />);

    await waitFor(() => {
      expect(screen.getByText("MACD Crossover")).toBeInTheDocument();
      expect(screen.getByText("by alice")).toBeInTheDocument();
      expect(screen.getByText("42 subscribers")).toBeInTheDocument();
    });
  });

  it("shows error state on fetch failure", async () => {
    vi.mocked(fetchMarketplaceStrategies).mockRejectedValue(
      new Error("Network error")
    );
    vi.mocked(fetchCategories).mockResolvedValue([]);
    render(<MarketplacePage />);

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("renders tab switcher", async () => {
    vi.mocked(fetchMarketplaceStrategies).mockResolvedValue(mockListings);
    vi.mocked(fetchCategories).mockResolvedValue(mockCategories);
    render(<MarketplacePage />);

    expect(screen.getByText("Marketplace")).toBeInTheDocument();
    expect(screen.getByText("Leaderboard")).toBeInTheDocument();
  });

  it("shows empty state when no strategies found", async () => {
    vi.mocked(fetchMarketplaceStrategies).mockResolvedValue({
      items: [],
      total: 0,
    });
    vi.mocked(fetchCategories).mockResolvedValue([]);
    render(<MarketplacePage />);

    await waitFor(() => {
      expect(
        screen.getByText("No strategies found matching your filters.")
      ).toBeInTheDocument();
    });
  });
});
