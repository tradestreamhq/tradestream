import { useState } from "react";
import { useSignalStream } from "@/hooks/useSignalStream";
import { SignalCard } from "@/components/signals/SignalCard";
import { cn } from "@/utils/utils";
import type { Signal } from "@/api/types";

type ActionFilter = "ALL" | "BUY" | "SELL" | "HOLD";

export function SignalFeedPage() {
  const { signals, isConnected, reconnect } = useSignalStream();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionFilter, setActionFilter] = useState<ActionFilter>("ALL");

  const filtered =
    actionFilter === "ALL"
      ? signals
      : signals.filter((s) => s.action === actionFilter);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      {/* Header */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Live Signal Feed</h1>
          <p className="mt-1 text-sm text-slate-400">
            Real-time trading signals from our AI strategy engine
          </p>
        </div>
        <div className="flex items-center gap-3">
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
      <div className="mb-6 flex gap-2">
        {(["ALL", "BUY", "SELL", "HOLD"] as const).map((action) => (
          <button
            key={action}
            onClick={() => setActionFilter(action)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
              actionFilter === action
                ? "bg-brand-500/20 text-brand-400"
                : "text-slate-400 hover:text-white"
            )}
          >
            {action}
          </button>
        ))}
      </div>

      {/* Signal list */}
      <div className="space-y-4" role="feed" aria-label="Trading signals">
        {filtered.length === 0 && (
          <div className="card text-center text-slate-500">
            {signals.length === 0
              ? "Waiting for signals..."
              : "No signals match the current filter."}
          </div>
        )}
        {filtered.map((signal: Signal) => (
          <SignalCard
            key={signal.signal_id}
            signal={signal}
            expanded={expandedId === signal.signal_id}
            onToggle={() =>
              setExpandedId(
                expandedId === signal.signal_id ? null : signal.signal_id
              )
            }
          />
        ))}
      </div>
    </div>
  );
}
