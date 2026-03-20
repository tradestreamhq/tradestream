import { useState, useEffect, useRef } from "react";
import { useSignalStream } from "@/hooks/useSignalStream";
import { useSoundAlert } from "@/hooks/useSoundAlert";
import { useDebounce } from "@/hooks/useDebounce";
import { SignalStream } from "@/components/signals/SignalStream";
import { PerformanceSidebar } from "@/components/signals/PerformanceSidebar";
import { PnLTracker } from "@/components/signals/PnLTracker";
import { cn } from "@/utils/utils";
import type { SignalFilters } from "@/api/types";

type ActionFilter = "ALL" | "BUY" | "SELL" | "HOLD";

export function SignalFeedPage() {
  const { signals, isConnected, reconnect } = useSignalStream();
  const [actionFilter, setActionFilter] = useState<ActionFilter>("ALL");
  const [minScore, setMinScore] = useState(0);
  const debouncedMinScore = useDebounce(minScore, 150);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const { triggerAlert } = useSoundAlert({ enabled: soundEnabled });
  const prevLengthRef = useRef(signals.length);

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

  // Build filters for SignalStream
  const filters: SignalFilters = {};
  if (actionFilter !== "ALL") {
    filters.actions = [actionFilter];
  }
  if (debouncedMinScore > 0) {
    filters.minOpportunityScore = debouncedMinScore;
  }

  return (
    <div className="mx-auto max-w-7xl px-2 py-4 sm:px-4 sm:py-6 lg:px-8">
      {/* Header */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4 sm:mb-6">
        <div>
          <h1 className="text-xl font-bold text-white sm:text-2xl">Live Signal Feed</h1>
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

      {/* Filters — sticky on mobile */}
      <div className="sticky top-0 z-10 -mx-2 mb-4 flex flex-wrap items-center gap-3 bg-surface/95 px-2 py-3 backdrop-blur-sm sm:static sm:mx-0 sm:mb-6 sm:bg-transparent sm:px-0 sm:py-0 sm:backdrop-blur-none">
        <div className="flex gap-2">
          {(["ALL", "BUY", "SELL", "HOLD"] as const).map((action) => (
            <button
              key={action}
              onClick={() => setActionFilter(action)}
              className={cn(
                "min-h-[44px] rounded-lg px-3 py-1.5 text-sm font-medium transition-colors sm:min-h-0",
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
        {/* Virtualized signal list */}
        <div className="min-w-0 flex-1">
          <SignalStream
            signals={signals}
            maxSignals={100}
            filters={filters}
            autoScroll={true}
            height={Math.max(400, window.innerHeight - 280)}
          />
        </div>

        {/* Performance sidebar */}
        <PerformanceSidebar signals={signals} />
      </div>
    </div>
  );
}
