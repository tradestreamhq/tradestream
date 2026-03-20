import { useEffect, useState, useMemo, useCallback } from "react";
import type {
  MarketplaceListing,
  LeaderboardEntry,
  CategoryInfo,
} from "@/api/types";
import {
  fetchMarketplaceStrategies,
  fetchLeaderboard,
  fetchCategories,
  subscribeToStrategy,
} from "@/api/marketplace";
import { cn, formatPercent } from "@/utils/utils";

type TabView = "marketplace" | "leaderboard";
type LeaderboardPeriod = "daily" | "weekly" | "monthly" | "all_time";
type LeaderboardSort =
  | "total_return_pct"
  | "sharpe_ratio"
  | "win_rate"
  | "consistency_score";

const CATEGORY_LABELS: Record<string, string> = {
  trend_following: "Trend Following",
  mean_reversion: "Mean Reversion",
  momentum: "Momentum",
  breakout: "Breakout",
  multi_indicator: "Multi-Indicator",
  volatility: "Volatility",
  statistical: "Statistical",
};

const PERIOD_LABELS: Record<string, string> = {
  daily: "24h",
  weekly: "7d",
  monthly: "30d",
  all_time: "All Time",
};

function PerformanceBadge({ value, label }: { value: number; label: string }) {
  const isPositive = value >= 0;
  return (
    <div className="text-center">
      <div className="text-xs text-slate-500">{label}</div>
      <div
        className={cn(
          "text-sm font-semibold",
          isPositive ? "text-emerald-400" : "text-red-400"
        )}
      >
        {isPositive ? "+" : ""}
        {label === "Sharpe" ? value.toFixed(2) : formatPercent(value)}
      </div>
    </div>
  );
}

function RatingStars({ rating, count }: { rating: number; count: number }) {
  const full = Math.floor(rating);
  const half = rating - full >= 0.5;
  return (
    <div className="flex items-center gap-1">
      {Array.from({ length: 5 }).map((_, i) => (
        <span
          key={i}
          className={cn(
            "text-xs",
            i < full
              ? "text-amber-400"
              : i === full && half
                ? "text-amber-400/50"
                : "text-slate-600"
          )}
        >
          *
        </span>
      ))}
      <span className="ml-1 text-xs text-slate-500">({count})</span>
    </div>
  );
}

function StrategyCard({
  listing,
  onSubscribe,
}: {
  listing: MarketplaceListing;
  onSubscribe: (id: string) => void;
}) {
  return (
    <div className="card flex flex-col gap-3 p-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-white">{listing.name}</h3>
          <p className="text-xs text-slate-500">by {listing.author}</p>
        </div>
        <span className="badge bg-brand-500/20 text-brand-400 text-xs">
          {CATEGORY_LABELS[listing.category] || listing.category}
        </span>
      </div>

      <p className="text-sm text-slate-400 line-clamp-2">
        {listing.description}
      </p>

      {listing.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {listing.tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className="rounded bg-slate-700/50 px-2 py-0.5 text-xs text-slate-400"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="grid grid-cols-3 gap-2 border-t border-slate-700/50 pt-3">
        {listing.live_metrics ? (
          <>
            <PerformanceBadge
              value={listing.live_metrics.total_return_pct / 100}
              label="Return"
            />
            <PerformanceBadge
              value={listing.live_metrics.sharpe_ratio}
              label="Sharpe"
            />
            <PerformanceBadge
              value={listing.live_metrics.win_rate}
              label="Win Rate"
            />
          </>
        ) : (
          <>
            <PerformanceBadge
              value={listing.performance_stats.total_return || 0}
              label="Return"
            />
            <PerformanceBadge
              value={listing.performance_stats.sharpe_ratio || 0}
              label="Sharpe"
            />
            <PerformanceBadge
              value={listing.performance_stats.win_rate || 0}
              label="Win Rate"
            />
          </>
        )}
      </div>

      <div className="flex items-center justify-between border-t border-slate-700/50 pt-3">
        <div className="flex items-center gap-3">
          <RatingStars rating={listing.avg_rating} count={listing.rating_count} />
          <span className="text-xs text-slate-500">
            {listing.subscribers_count} subscribers
          </span>
        </div>
        <button
          onClick={() => onSubscribe(listing.id)}
          className="rounded-md bg-brand-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-600 transition-colors"
        >
          Subscribe
        </button>
      </div>
    </div>
  );
}

export function MarketplacePage() {
  const [tab, setTab] = useState<TabView>("marketplace");
  const [listings, setListings] = useState<MarketplaceListing[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [orderBy, setOrderBy] = useState("subscribers_count");

  // Leaderboard controls
  const [period, setPeriod] = useState<LeaderboardPeriod>("monthly");
  const [lbSort, setLbSort] = useState<LeaderboardSort>("total_return_pct");

  // Comparison
  const [compareIds, setCompareIds] = useState<Set<string>>(new Set());

  const loadCategories = useCallback(async () => {
    try {
      const cats = await fetchCategories();
      setCategories(cats);
    } catch {
      // categories are optional
    }
  }, []);

  const loadMarketplace = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { items } = await fetchMarketplaceStrategies({
        category: selectedCategory || undefined,
        search: searchQuery || undefined,
        order_by: orderBy,
      });
      setListings(items);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [selectedCategory, searchQuery, orderBy]);

  const loadLeaderboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { items } = await fetchLeaderboard(
        period,
        lbSort,
        selectedCategory || undefined
      );
      setLeaderboard(items);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [period, lbSort, selectedCategory]);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  useEffect(() => {
    if (tab === "marketplace") {
      loadMarketplace();
    } else {
      loadLeaderboard();
    }
  }, [tab, loadMarketplace, loadLeaderboard]);

  const handleSubscribe = async (listingId: string) => {
    try {
      await subscribeToStrategy(listingId, "current-user");
      loadMarketplace();
    } catch {
      // silent for now
    }
  };

  const toggleCompare = (id: string) => {
    setCompareIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < 5) {
        next.add(id);
      }
      return next;
    });
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">
          Strategy Marketplace
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Browse, compare, and subscribe to trading strategies ranked by
          performance
        </p>
      </div>

      {/* Tab Switcher */}
      <div className="mb-6 flex gap-1 rounded-lg bg-slate-800/50 p-1 w-fit">
        {(["marketplace", "leaderboard"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "rounded-md px-4 py-2 text-sm font-medium transition-colors",
              tab === t
                ? "bg-brand-500 text-white"
                : "text-slate-400 hover:text-white"
            )}
          >
            {t === "marketplace" ? "Marketplace" : "Leaderboard"}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        {/* Category filter */}
        <select
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          className="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
        >
          <option value="">All Categories</option>
          {categories.map((cat) => (
            <option key={cat.name} value={cat.name}>
              {cat.label}
            </option>
          ))}
        </select>

        {tab === "marketplace" && (
          <>
            {/* Search */}
            <input
              type="text"
              placeholder="Search strategies..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 w-64"
            />
            {/* Sort */}
            <select
              value={orderBy}
              onChange={(e) => setOrderBy(e.target.value)}
              className="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
            >
              <option value="subscribers_count">Most Popular</option>
              <option value="avg_rating">Highest Rated</option>
              <option value="created_at">Newest</option>
              <option value="price">Price</option>
            </select>
          </>
        )}

        {tab === "leaderboard" && (
          <>
            {/* Period selector */}
            <div className="flex gap-1 rounded-lg bg-slate-800/50 p-1">
              {(
                ["daily", "weekly", "monthly", "all_time"] as const
              ).map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={cn(
                    "rounded-md px-3 py-1 text-xs font-medium transition-colors",
                    period === p
                      ? "bg-brand-500 text-white"
                      : "text-slate-400 hover:text-white"
                  )}
                >
                  {PERIOD_LABELS[p]}
                </button>
              ))}
            </div>
            {/* Sort metric */}
            <select
              value={lbSort}
              onChange={(e) =>
                setLbSort(e.target.value as LeaderboardSort)
              }
              className="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
            >
              <option value="total_return_pct">Total Return</option>
              <option value="sharpe_ratio">Sharpe Ratio</option>
              <option value="win_rate">Win Rate</option>
              <option value="consistency_score">Consistency</option>
            </select>
          </>
        )}
      </div>

      {/* Loading / Error */}
      {loading && (
        <div className="card animate-pulse space-y-4 p-8">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-10 rounded bg-slate-700/50" />
          ))}
        </div>
      )}

      {error && !loading && (
        <div className="card text-center text-red-400 p-4">{error}</div>
      )}

      {/* Marketplace Grid */}
      {!loading && !error && tab === "marketplace" && (
        <>
          {listings.length === 0 ? (
            <div className="card p-8 text-center text-slate-400">
              No strategies found matching your filters.
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {listings.map((listing) => (
                <StrategyCard
                  key={listing.id}
                  listing={listing}
                  onSubscribe={handleSubscribe}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Leaderboard Table */}
      {!loading && !error && tab === "leaderboard" && (
        <div className="overflow-x-auto">
          {leaderboard.length === 0 ? (
            <div className="card p-8 text-center text-slate-400">
              No leaderboard data available for this period.
            </div>
          ) : (
            <table className="w-full">
              <thead className="border-b border-slate-700/50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Rank
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Strategy
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Category
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Return
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Sharpe
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Win Rate
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Max DD
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Trades
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Consistency
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/30">
                {leaderboard.map((entry) => (
                  <tr
                    key={entry.strategy_id}
                    className="transition-colors hover:bg-surface-card/50"
                  >
                    <td className="px-4 py-3 text-sm font-bold text-slate-500">
                      #{entry.rank}
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-white">
                        {entry.name || entry.strategy_id.slice(0, 8)}
                      </div>
                      {entry.author && (
                        <div className="text-xs text-slate-500">
                          by {entry.author}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-400">
                      {entry.category
                        ? CATEGORY_LABELS[entry.category] || entry.category
                        : "-"}
                    </td>
                    <td
                      className={cn(
                        "px-4 py-3 text-right text-sm font-medium",
                        entry.total_return_pct >= 0
                          ? "text-emerald-400"
                          : "text-red-400"
                      )}
                    >
                      {entry.total_return_pct >= 0 ? "+" : ""}
                      {entry.total_return_pct.toFixed(2)}%
                    </td>
                    <td className="px-4 py-3 text-right text-sm font-medium text-white">
                      {entry.sharpe_ratio.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-right text-sm font-medium text-white">
                      {formatPercent(entry.win_rate)}
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-red-400">
                      {entry.max_drawdown_pct.toFixed(2)}%
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-slate-300">
                      {entry.trade_count}
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-slate-300">
                      {(entry.consistency_score * 100).toFixed(0)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
