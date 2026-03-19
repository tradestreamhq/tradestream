import { useEffect, useState, useCallback } from "react";
import type { Signal, SignalFilters } from "@/api/types";
import { fetchSignals } from "@/api/client";
import { cn, formatPercent, formatPrice, formatDate, formatTime } from "@/utils/utils";

type OutcomeFilter = "ALL" | "WIN" | "LOSS" | "PENDING";

export function SignalHistoryPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [symbolSearch, setSymbolSearch] = useState("");
  const [actionFilter, setActionFilter] = useState<"ALL" | "BUY" | "SELL" | "HOLD">("ALL");
  const [outcomeFilter, setOutcomeFilter] = useState<OutcomeFilter>("ALL");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const loadSignals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters: SignalFilters = {};
      if (symbolSearch.trim()) filters.symbols = [symbolSearch.trim().toUpperCase()];
      if (actionFilter !== "ALL") filters.actions = [actionFilter];
      if (outcomeFilter !== "ALL") filters.outcomes = [outcomeFilter];
      if (dateFrom) filters.dateFrom = dateFrom;
      if (dateTo) filters.dateTo = dateTo;
      const data = await fetchSignals(filters);
      setSignals(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load signals");
    } finally {
      setLoading(false);
    }
  }, [symbolSearch, actionFilter, outcomeFilter, dateFrom, dateTo]);

  useEffect(() => {
    loadSignals();
  }, [loadSignals]);

  const stats = {
    total: signals.length,
    wins: signals.filter((s) => s.outcome === "WIN").length,
    losses: signals.filter((s) => s.outcome === "LOSS").length,
    pending: signals.filter((s) => s.outcome === "PENDING").length,
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Signal History</h1>
        <p className="mt-1 text-sm text-slate-400">
          Browse and filter past signals with outcomes
        </p>
      </div>

      {/* Summary stats */}
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="card py-4 text-center">
          <div className="text-xl font-bold text-white">{stats.total}</div>
          <div className="text-xs text-slate-400">Total</div>
        </div>
        <div className="card py-4 text-center">
          <div className="text-xl font-bold text-emerald-400">{stats.wins}</div>
          <div className="text-xs text-slate-400">Wins</div>
        </div>
        <div className="card py-4 text-center">
          <div className="text-xl font-bold text-red-400">{stats.losses}</div>
          <div className="text-xs text-slate-400">Losses</div>
        </div>
        <div className="card py-4 text-center">
          <div className="text-xl font-bold text-amber-400">{stats.pending}</div>
          <div className="text-xs text-slate-400">Pending</div>
        </div>
      </div>

      {/* Filters */}
      <div className="card mb-6">
        <div className="flex flex-wrap gap-4">
          <div className="w-full sm:w-auto">
            <label htmlFor="symbol-search" className="mb-1 block text-xs text-slate-400">
              Symbol
            </label>
            <input
              id="symbol-search"
              type="text"
              placeholder="e.g. BTC/USD"
              value={symbolSearch}
              onChange={(e) => setSymbolSearch(e.target.value)}
              className="input w-full sm:w-40"
            />
          </div>
          <div>
            <label htmlFor="action-filter" className="mb-1 block text-xs text-slate-400">
              Action
            </label>
            <select
              id="action-filter"
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value as typeof actionFilter)}
              className="input"
            >
              <option value="ALL">All</option>
              <option value="BUY">Buy</option>
              <option value="SELL">Sell</option>
              <option value="HOLD">Hold</option>
            </select>
          </div>
          <div>
            <label htmlFor="outcome-filter" className="mb-1 block text-xs text-slate-400">
              Outcome
            </label>
            <select
              id="outcome-filter"
              value={outcomeFilter}
              onChange={(e) => setOutcomeFilter(e.target.value as OutcomeFilter)}
              className="input"
            >
              <option value="ALL">All</option>
              <option value="WIN">Win</option>
              <option value="LOSS">Loss</option>
              <option value="PENDING">Pending</option>
            </select>
          </div>
          <div>
            <label htmlFor="date-from" className="mb-1 block text-xs text-slate-400">
              From
            </label>
            <input
              id="date-from"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="input"
            />
          </div>
          <div>
            <label htmlFor="date-to" className="mb-1 block text-xs text-slate-400">
              To
            </label>
            <input
              id="date-to"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="input"
            />
          </div>
        </div>
      </div>

      {/* Results */}
      {loading ? (
        <div className="card animate-pulse space-y-3 p-8">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-8 rounded bg-slate-700/50" />
          ))}
        </div>
      ) : error ? (
        <div className="card text-center text-red-400">{error}</div>
      ) : signals.length === 0 ? (
        <div className="card text-center text-slate-500">
          No signals found matching your filters.
        </div>
      ) : (
        <>
          {/* Mobile cards */}
          <div className="space-y-3 lg:hidden">
            {signals.map((s) => (
              <div key={s.signal_id} className="card">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white">{s.symbol}</span>
                    <span
                      className={cn(
                        "badge",
                        s.action === "BUY" && "badge-buy",
                        s.action === "SELL" && "badge-sell",
                        s.action === "HOLD" && "badge-hold"
                      )}
                    >
                      {s.action}
                    </span>
                  </div>
                  {s.outcome && (
                    <span
                      className={cn(
                        "badge",
                        s.outcome === "WIN" && "bg-emerald-500/20 text-emerald-400",
                        s.outcome === "LOSS" && "bg-red-500/20 text-red-400",
                        s.outcome === "PENDING" && "bg-amber-500/20 text-amber-400"
                      )}
                    >
                      {s.outcome}
                    </span>
                  )}
                </div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
                  <span>Entry: {formatPrice(s.entry_price)}</span>
                  <span>Conf: {formatPercent(s.confidence)}</span>
                  <span>{formatDate(s.timestamp)}</span>
                  {s.pnl_percent != null && (
                    <span
                      className={cn(
                        "font-medium",
                        s.pnl_percent >= 0 ? "text-emerald-400" : "text-red-400"
                      )}
                    >
                      {s.pnl_percent >= 0 ? "+" : ""}
                      {(s.pnl_percent * 100).toFixed(2)}%
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Desktop table */}
          <div className="hidden overflow-x-auto lg:block">
            <table className="w-full">
              <thead className="border-b border-slate-700/50">
                <tr>
                  {["Date", "Symbol", "Action", "Entry", "SL", "TP", "Confidence", "Outcome", "P&L"].map(
                    (h) => (
                      <th
                        key={h}
                        className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400"
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/30">
                {signals.map((s) => (
                  <tr
                    key={s.signal_id}
                    className="transition-colors hover:bg-surface-card/50"
                  >
                    <td className="px-4 py-3 text-sm text-slate-300">
                      <div>{formatDate(s.timestamp)}</div>
                      <div className="text-xs text-slate-500">
                        {formatTime(s.timestamp)}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-white">
                      {s.symbol}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "badge",
                          s.action === "BUY" && "badge-buy",
                          s.action === "SELL" && "badge-sell",
                          s.action === "HOLD" && "badge-hold"
                        )}
                      >
                        {s.action}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-300">
                      {formatPrice(s.entry_price)}
                    </td>
                    <td className="px-4 py-3 text-sm text-red-400">
                      {formatPrice(s.stop_loss)}
                    </td>
                    <td className="px-4 py-3 text-sm text-emerald-400">
                      {formatPrice(s.take_profit)}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-300">
                      {formatPercent(s.confidence)}
                    </td>
                    <td className="px-4 py-3">
                      {s.outcome && (
                        <span
                          className={cn(
                            "badge",
                            s.outcome === "WIN" && "bg-emerald-500/20 text-emerald-400",
                            s.outcome === "LOSS" && "bg-red-500/20 text-red-400",
                            s.outcome === "PENDING" && "bg-amber-500/20 text-amber-400"
                          )}
                        >
                          {s.outcome}
                        </span>
                      )}
                    </td>
                    <td
                      className={cn(
                        "px-4 py-3 text-sm font-medium",
                        s.pnl_percent != null && s.pnl_percent >= 0
                          ? "text-emerald-400"
                          : "text-red-400"
                      )}
                    >
                      {s.pnl_percent != null
                        ? `${s.pnl_percent >= 0 ? "+" : ""}${(s.pnl_percent * 100).toFixed(2)}%`
                        : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
