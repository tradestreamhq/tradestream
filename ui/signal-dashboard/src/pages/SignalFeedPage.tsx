import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { useSignalStream } from "@/hooks/useSignalStream";
import { useSoundAlert } from "@/hooks/useSoundAlert";
import { SignalCard } from "@/components/signals/SignalCard";
import { PerformanceSidebar } from "@/components/signals/PerformanceSidebar";
import { PnLTracker } from "@/components/signals/PnLTracker";
import { cn } from "@/utils/utils";
import type { Signal } from "@/api/types";

type ActionFilter = "ALL" | "BUY" | "SELL" | "HOLD";

export function SignalFeedPage() {
  const { signals, isConnected, reconnect } = useSignalStream();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionFilter, setActionFilter] = useState<ActionFilter>("ALL");
  const [minScore, setMinScore] = useState(0);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const { triggerAlert } = useSoundAlert({ enabled: soundEnabled });
  const prevLengthRef = useRef(signals.length);
  const listRef = useRef<HTMLDivElement>(null);

  // Sound alert when new signal arrives
  useEffect(() => {
    if (signals.length > prevLengthRef.current && prevLengthRef.current > 0) {
      const newest = signals[0];
      if (newest) {
        triggerAlert(newest.action === "BUY" ? "buy" : newest.action === "SELL" ? "sell" : "default");
      }
    }
    prevLengthRef.current = signals.length;
  }, [signals.length, signals, triggerAlert]);

  // Filter and sort signals
  const filtered = useMemo(() => {
    let result = actionFilter === "ALL"
      ? signals
      : signals.filter((s) => s.action === actionFilter);

    if (minScore > 0) {
      result = result.filter((s) => s.opportunity_score >= minScore);
    }

    return result.sort((a, b) => b.opportunity_score - a.opportunity_score);
  }, [signals, actionFilter, minScore]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          setFocusedIndex((prev) => Math.min(prev + 1, filtered.length - 1));
          break;
        case "ArrowUp":
          event.preventDefault();
          setFocusedIndex((prev) => Math.max(prev - 1, 0));
          break;
        case "Enter":
        case " ":
          event.preventDefault();
          if (focusedIndex >= 0 && focusedIndex < filtered.length) {
            const signal = filtered[focusedIndex];
            setExpandedId(expandedId === signal.signal_id ? null : signal.signal_id);
          }
          break;
        case "Escape":
          setExpandedId(null);
          break;
      }
    },
    [focusedIndex, filtered, expandedId]
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Live Signal Feed</h1>
          <p className="mt-1 text-sm text-slate-400">
            Real-time trading signals sorted by opportunity score
          </p>
        </div>
        <div className="flex items-center gap-4">
          <PnLTracker signals={signals} />
          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
              soundEnabled
                ? "bg-brand-500/20 text-brand-400"
                : "text-slate-500 hover:text-slate-300"
            )}
            aria-label={soundEnabled ? "Mute sound alerts" : "Enable sound alerts"}
          >
            {soundEnabled ? "\uD83D\uDD0A Sound On" : "\uD83D\uDD07 Sound Off"}
          </button>
          <span
            className={cn(
              "inline-flex items-center gap-1.5 text-xs font-medium",
              isConnected ? "text-emerald-400" : "text-red-400"
            )}
          >
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                isConnected ? "bg-emerald-400 animate-pulse" : "bg-red-400"
              )}
            />
            {isConnected ? "Live" : "Disconnected"}
          </span>
          {!isConnected && (
            <button
              onClick={reconnect}
              className="text-xs text-brand-400 hover:underline"
            >
              Reconnect
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="flex gap-2">
          {(["ALL", "BUY", "SELL", "HOLD"] as const).map((action) => (
            <button
              key={action}
              onClick={() => setActionFilter(action)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                actionFilter === action
                  ? action === "BUY"
                    ? "bg-emerald-500/20 text-emerald-400"
                    : action === "SELL"
                    ? "bg-red-500/20 text-red-400"
                    : action === "HOLD"
                    ? "bg-amber-500/20 text-amber-400"
                    : "bg-brand-500/20 text-brand-400"
                  : "text-slate-400 hover:text-white"
              )}
            >
              {action}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="min-score" className="text-xs text-slate-500">
            Min score:
          </label>
          <input
            id="min-score"
            type="range"
            min={0}
            max={100}
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="h-1.5 w-24 cursor-pointer appearance-none rounded-full bg-slate-700 accent-brand-500"
          />
          <span className="w-8 text-right text-xs font-medium text-slate-400">
            {minScore}
          </span>
        </div>
      </div>

      {/* Main layout: signals + sidebar */}
      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Signal list */}
        <div
          ref={listRef}
          className="min-w-0 flex-1 space-y-4"
          role="feed"
          aria-label="Trading signals sorted by opportunity score"
          tabIndex={0}
          onKeyDown={handleKeyDown}
        >
          {filtered.length === 0 && (
            <div className="card text-center text-slate-500">
              {signals.length === 0
                ? "Waiting for signals..."
                : "No signals match the current filters."}
            </div>
          )}
          {filtered.map((signal: Signal, index: number) => (
            <SignalCard
              key={signal.signal_id}
              signal={signal}
              expanded={expandedId === signal.signal_id}
              isFocused={focusedIndex === index}
              onToggle={() =>
                setExpandedId(
                  expandedId === signal.signal_id ? null : signal.signal_id
                )
              }
            />
          ))}

          {/* Live region for screen reader */}
          <div
            role="status"
            aria-live="polite"
            aria-atomic="true"
            className="sr-only"
          >
            {filtered.length} signals available
          </div>
        </div>

        {/* Performance sidebar */}
        <PerformanceSidebar signals={signals} />
      </div>
    </div>
  );
}
