import { useEffect, useState, useMemo } from "react";
import type { Strategy } from "@/api/types";
import { fetchStrategies } from "@/api/client";
import { cn, formatPercent } from "@/utils/utils";

type SortKey =
  | "win_rate"
  | "sharpe_ratio"
  | "total_return"
  | "total_signals"
  | "max_drawdown";

export function StrategyLeaderboardPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("win_rate");
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    fetchStrategies()
      .then(setStrategies)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const sorted = useMemo(() => {
    const copy = [...strategies];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      return sortAsc ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return copy;
  }, [strategies, sortKey, sortAsc]);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  }

  function SortHeader({
    label,
    field,
  }: {
    label: string;
    field: SortKey;
  }) {
    return (
      <th
        className="cursor-pointer px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400 hover:text-white"
        onClick={() => handleSort(field)}
        aria-sort={
          sortKey === field
            ? sortAsc
              ? "ascending"
              : "descending"
            : "none"
        }
      >
        <span className="inline-flex items-center gap-1">
          {label}
          {sortKey === field && (
            <span className="text-brand-400">{sortAsc ? "\u2191" : "\u2193"}</span>
          )}
        </span>
      </th>
    );
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <h1 className="mb-6 text-2xl font-bold text-white">
          Strategy Leaderboard
        </h1>
        <div className="card animate-pulse space-y-4 p-8">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-10 rounded bg-slate-700/50" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <h1 className="mb-6 text-2xl font-bold text-white">
          Strategy Leaderboard
        </h1>
        <div className="card text-center text-red-400">{error}</div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Strategy Leaderboard</h1>
        <p className="mt-1 text-sm text-slate-400">
          Strategies ranked by performance metrics
        </p>
      </div>

      {/* Mobile cards */}
      <div className="space-y-4 lg:hidden">
        {sorted.map((s, i) => (
          <div key={s.strategy_id} className="card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-lg font-bold text-slate-500">
                  #{i + 1}
                </span>
                <span className="font-semibold text-white">{s.name}</span>
              </div>
              <span
                className={cn(
                  "badge",
                  s.active
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "bg-slate-600/30 text-slate-500"
                )}
              >
                {s.active ? "Active" : "Inactive"}
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-400">{s.description}</p>
            <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-slate-500">Win Rate </span>
                <span className="font-medium text-white">
                  {formatPercent(s.win_rate)}
                </span>
              </div>
              <div>
                <span className="text-slate-500">Sharpe </span>
                <span className="font-medium text-white">
                  {s.sharpe_ratio.toFixed(2)}
                </span>
              </div>
              <div>
                <span className="text-slate-500">Return </span>
                <span
                  className={cn(
                    "font-medium",
                    s.total_return >= 0 ? "text-emerald-400" : "text-red-400"
                  )}
                >
                  {s.total_return >= 0 ? "+" : ""}
                  {formatPercent(s.total_return)}
                </span>
              </div>
              <div>
                <span className="text-slate-500">Signals </span>
                <span className="font-medium text-white">
                  {s.total_signals}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Desktop table */}
      <div className="hidden overflow-x-auto lg:block">
        <table className="w-full">
          <thead className="border-b border-slate-700/50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
                #
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
                Strategy
              </th>
              <SortHeader label="Win Rate" field="win_rate" />
              <SortHeader label="Sharpe" field="sharpe_ratio" />
              <SortHeader label="Total Return" field="total_return" />
              <SortHeader label="Signals" field="total_signals" />
              <SortHeader label="Max Drawdown" field="max_drawdown" />
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/30">
            {sorted.map((s, i) => (
              <tr
                key={s.strategy_id}
                className="transition-colors hover:bg-surface-card/50"
              >
                <td className="px-4 py-3 text-sm font-bold text-slate-500">
                  {i + 1}
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium text-white">{s.name}</div>
                  <div className="text-xs text-slate-500">{s.description}</div>
                </td>
                <td className="px-4 py-3 text-sm font-medium text-white">
                  {formatPercent(s.win_rate)}
                </td>
                <td className="px-4 py-3 text-sm font-medium text-white">
                  {s.sharpe_ratio.toFixed(2)}
                </td>
                <td
                  className={cn(
                    "px-4 py-3 text-sm font-medium",
                    s.total_return >= 0 ? "text-emerald-400" : "text-red-400"
                  )}
                >
                  {s.total_return >= 0 ? "+" : ""}
                  {formatPercent(s.total_return)}
                </td>
                <td className="px-4 py-3 text-sm text-slate-300">
                  {s.total_signals}
                </td>
                <td className="px-4 py-3 text-sm text-red-400">
                  {formatPercent(s.max_drawdown)}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={cn(
                      "badge",
                      s.active
                        ? "bg-emerald-500/20 text-emerald-400"
                        : "bg-slate-600/30 text-slate-500"
                    )}
                  >
                    {s.active ? "Active" : "Inactive"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
