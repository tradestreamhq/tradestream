import React, { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { VariableSizeList as List } from "react-window";
import type { AgentEvent, Signal, SignalAction, SignalFilters } from "../types";
import { SignalCard } from "./SignalCard";
import { SignalStreamErrorBoundary } from "./SignalStreamErrorBoundary";
import { PnLTracker } from "./PnLTracker";
import { useSignalStream } from "../hooks/useSignalStream";
import { useSoundAlert } from "../hooks/useSoundAlert";

const COLLAPSED_ROW_HEIGHT = 160;
const EXPANDED_ROW_HEIGHT = 520;

interface SignalStreamProps {
  events: AgentEvent[];
  title?: string;
  maxSignals?: number;
  autoScroll?: boolean;
  soundEnabled?: boolean;
}

function FilterBar({
  filters,
  onFilterChange,
  signalCount,
}: {
  filters: SignalFilters;
  onFilterChange: (f: SignalFilters) => void;
  signalCount: number;
}) {
  const activeActions = filters.actions || [];
  const minScore = filters.minOpportunityScore ?? 0;

  const toggleAction = (action: SignalAction) => {
    const current = activeActions;
    const next = current.includes(action)
      ? current.filter((a) => a !== action)
      : [...current, action];
    onFilterChange({ ...filters, actions: next.length > 0 ? next : undefined });
  };

  return (
    <div className="filter-bar" role="toolbar" aria-label="Signal filters">
      <div className="filter-buttons">
        {(["BUY", "SELL", "HOLD"] as SignalAction[]).map((action) => (
          <button
            key={action}
            className={`filter-btn ${action.toLowerCase()} ${activeActions.includes(action) ? "active" : ""}`}
            onClick={() => toggleAction(action)}
            aria-pressed={activeActions.includes(action)}
          >
            {action}
          </button>
        ))}
      </div>
      <div className="filter-score">
        <label htmlFor="min-score">Min score:</label>
        <input
          id="min-score"
          type="range"
          min={0}
          max={100}
          value={minScore}
          onChange={(e) =>
            onFilterChange({
              ...filters,
              minOpportunityScore: Number(e.target.value) || undefined,
            })
          }
        />
        <span className="score-label">{minScore}</span>
      </div>
      <div className="filter-count">{signalCount} signals</div>
    </div>
  );
}

export function SignalStream({
  events,
  title = "Top Opportunities",
  maxSignals = 100,
  autoScroll = true,
  soundEnabled = true,
}: SignalStreamProps) {
  const [filters, setFilters] = useState<SignalFilters>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const listRef = useRef<List>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const { signals, hasNewSignal, latestSignal } = useSignalStream({
    events,
    filters,
    maxSignals,
  });

  const { playBuyAlert, playSellAlert, playHotAlert } = useSoundAlert({
    enabled: soundEnabled,
  });

  // Sound alerts for new signals
  useEffect(() => {
    if (!hasNewSignal || !latestSignal) return;
    if (latestSignal.opportunity_tier === "HOT") playHotAlert();
    else if (latestSignal.action === "BUY") playBuyAlert();
    else if (latestSignal.action === "SELL") playSellAlert();
  }, [hasNewSignal, latestSignal, playBuyAlert, playSellAlert, playHotAlert]);

  // Dynamic row height
  const getItemSize = useCallback(
    (index: number) => {
      const signal = signals[index];
      return signal?.signal_id === expandedId ? EXPANDED_ROW_HEIGHT : COLLAPSED_ROW_HEIGHT;
    },
    [expandedId, signals]
  );

  // Reset list measurements when expansion changes
  useEffect(() => {
    listRef.current?.resetAfterIndex(0);
  }, [expandedId]);

  // Auto-scroll to top on new signals
  useEffect(() => {
    if (autoScroll && !isHovered && listRef.current) {
      listRef.current.scrollToItem(0);
    }
  }, [signals.length, autoScroll, isHovered]);

  // Get events for a specific signal
  const getEventsForSignal = useCallback(
    (signalId: string) =>
      events.filter((e) => e.signal_id === signalId),
    [events]
  );

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          setFocusedIndex((prev) => Math.min(prev + 1, signals.length - 1));
          break;
        case "ArrowUp":
          event.preventDefault();
          setFocusedIndex((prev) => Math.max(prev - 1, 0));
          break;
        case "Enter":
        case " ":
          event.preventDefault();
          if (focusedIndex >= 0 && focusedIndex < signals.length) {
            const signal = signals[focusedIndex];
            setExpandedId(expandedId === signal.signal_id ? null : signal.signal_id);
          }
          break;
        case "Escape":
          setExpandedId(null);
          break;
      }
    },
    [focusedIndex, signals, expandedId]
  );

  // Scroll focused item into view
  useEffect(() => {
    if (focusedIndex >= 0) {
      listRef.current?.scrollToItem(focusedIndex, "smart");
    }
  }, [focusedIndex]);

  const Row = useCallback(
    ({ index, style }: { index: number; style: React.CSSProperties }) => {
      const signal = signals[index];
      if (!signal) return null;
      return (
        <div style={style} role="listitem" aria-posinset={index + 1} aria-setsize={signals.length}>
          <SignalCard
            signal={signal}
            isExpanded={expandedId === signal.signal_id}
            isFocused={focusedIndex === index}
            onToggleExpand={() =>
              setExpandedId(expandedId === signal.signal_id ? null : signal.signal_id)
            }
            events={getEventsForSignal(signal.signal_id)}
          />
        </div>
      );
    },
    [signals, expandedId, focusedIndex, getEventsForSignal]
  );

  // Calculate container height (responsive)
  const listHeight = typeof window !== "undefined" ? Math.min(window.innerHeight - 300, 600) : 600;

  return (
    <SignalStreamErrorBoundary>
      <div className="signal-stream-v2">
        <div className="signal-stream-header-v2">
          <span className="signal-stream-title">{title}</span>
        </div>
        <FilterBar
          filters={filters}
          onFilterChange={setFilters}
          signalCount={signals.length}
        />
        <div className="signal-stream-layout">
          <div
            className="signal-list-v2"
            ref={containerRef}
            role="list"
            aria-label="Trading signals sorted by opportunity score"
            tabIndex={0}
            onKeyDown={handleKeyDown}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
          >
            {signals.length === 0 ? (
              <div className="empty-state">No signals match your filters. Waiting for agent activity...</div>
            ) : (
              <List
                ref={listRef}
                height={listHeight}
                itemCount={signals.length}
                itemSize={getItemSize}
                width="100%"
              >
                {Row}
              </List>
            )}
          </div>
          <div className="signal-sidebar">
            <PnLTracker signals={signals} />
          </div>
        </div>
        {/* Live region for screen reader announcements */}
        <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
          {signals.length} signals available
        </div>
      </div>
    </SignalStreamErrorBoundary>
  );
}
