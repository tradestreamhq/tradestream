import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { VariableSizeList as List } from "react-window";
import { SignalCard } from "./SignalCard";
import { SignalStreamErrorBoundary } from "./SignalStreamErrorBoundary";
import type { Signal, SignalFilters } from "@/api/types";

const COLLAPSED_ROW_HEIGHT = 120;
const EXPANDED_ROW_HEIGHT = 480;
const ROW_GAP = 16;

interface SignalStreamProps {
  signals: Signal[];
  maxSignals?: number;
  filters?: SignalFilters;
  onSignalClick?: (signal: Signal) => void;
  autoScroll?: boolean;
  height?: number;
}

export function SignalStream({
  signals,
  maxSignals = 100,
  filters = {},
  onSignalClick,
  autoScroll = true,
  height = 600,
}: SignalStreamProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState<number>(-1);
  const listRef = useRef<List>(null);

  // Filter and sort signals
  const filteredSignals = useMemo(() => {
    let result = signals.slice(0, maxSignals);

    if (filters.actions?.length) {
      result = result.filter((s) => filters.actions!.includes(s.action));
    }
    if (filters.minConfidence) {
      result = result.filter((s) => s.confidence >= filters.minConfidence!);
    }
    if (filters.minOpportunityScore) {
      result = result.filter(
        (s) => s.opportunity_score >= filters.minOpportunityScore!
      );
    }

    return result.sort((a, b) => b.opportunity_score - a.opportunity_score);
  }, [signals, filters, maxSignals]);

  // Dynamic row height based on expanded state
  const getItemSize = useCallback(
    (index: number) => {
      const signal = filteredSignals[index];
      const baseHeight =
        signal?.signal_id === expandedId
          ? EXPANDED_ROW_HEIGHT
          : COLLAPSED_ROW_HEIGHT;
      return baseHeight + ROW_GAP;
    },
    [expandedId, filteredSignals]
  );

  // Reset list measurements when expansion state changes
  useEffect(() => {
    if (listRef.current) {
      listRef.current.resetAfterIndex(0);
    }
  }, [expandedId]);

  // Auto-scroll to top when new signal arrives
  useEffect(() => {
    if (autoScroll && !isHovered && listRef.current) {
      listRef.current.scrollToItem(0);
    }
  }, [signals.length, autoScroll, isHovered]);

  // Keyboard navigation handler
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          setFocusedIndex((prev) =>
            Math.min(prev + 1, filteredSignals.length - 1)
          );
          break;
        case "ArrowUp":
          event.preventDefault();
          setFocusedIndex((prev) => Math.max(prev - 1, 0));
          break;
        case "Enter":
        case " ":
          event.preventDefault();
          if (focusedIndex >= 0 && focusedIndex < filteredSignals.length) {
            const signal = filteredSignals[focusedIndex];
            setExpandedId(
              expandedId === signal.signal_id ? null : signal.signal_id
            );
            onSignalClick?.(signal);
          }
          break;
        case "Escape":
          setExpandedId(null);
          break;
      }
    },
    [focusedIndex, filteredSignals, expandedId, onSignalClick]
  );

  // Scroll focused item into view
  useEffect(() => {
    if (focusedIndex >= 0 && listRef.current) {
      listRef.current.scrollToItem(focusedIndex, "smart");
    }
  }, [focusedIndex]);

  const Row = ({
    index,
    style,
  }: {
    index: number;
    style: React.CSSProperties;
  }) => {
    const signal = filteredSignals[index];
    const isExpanded = expandedId === signal.signal_id;

    return (
      <div
        style={{ ...style, paddingBottom: ROW_GAP }}
        role="listitem"
        aria-posinset={index + 1}
        aria-setsize={filteredSignals.length}
      >
        <SignalCard
          signal={signal}
          expanded={isExpanded}
          isFocused={focusedIndex === index}
          onToggle={() => {
            setExpandedId(isExpanded ? null : signal.signal_id);
            onSignalClick?.(signal);
          }}
        />
      </div>
    );
  };

  return (
    <SignalStreamErrorBoundary>
      <div
        className="signal-stream"
        role="list"
        aria-label="Trading signals sorted by opportunity score"
        tabIndex={0}
        onKeyDown={handleKeyDown}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {filteredSignals.length === 0 ? (
          <div className="card text-center text-slate-500">
            {signals.length === 0
              ? "Waiting for signals..."
              : "No signals match the current filters."}
          </div>
        ) : (
          <List
            ref={listRef}
            height={height}
            itemCount={filteredSignals.length}
            itemSize={getItemSize}
            width="100%"
          >
            {Row}
          </List>
        )}
        {/* Live region for screen reader announcements */}
        <div
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className="sr-only"
        >
          {filteredSignals.length} signals available
        </div>
      </div>
    </SignalStreamErrorBoundary>
  );
}
