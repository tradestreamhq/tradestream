import React from "react";
import type { AgentEvent, Signal } from "../types";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { ToolCallLog } from "./ToolCallLog";
import { StrategyBreakdown } from "./StrategyBreakdown";

interface SignalCardProps {
  signal: Signal;
  isExpanded: boolean;
  isFocused?: boolean;
  onToggleExpand: () => void;
  events?: AgentEvent[];
}

function getTierIcon(tier: string): string {
  switch (tier) {
    case "HOT": return "\uD83D\uDD25";
    case "GOOD": return "\u2B50";
    case "NEUTRAL": return "\u26AA";
    default: return "\uD83D\uDD39";
  }
}

function getTierLabel(tier: string): string {
  switch (tier) {
    case "HOT": return "Hot opportunity";
    case "GOOD": return "Good opportunity";
    case "NEUTRAL": return "Neutral opportunity";
    default: return "Opportunity";
  }
}

function getActionClass(action: string): string {
  switch (action) {
    case "BUY": return "action-buy";
    case "SELL": return "action-sell";
    default: return "action-hold";
  }
}

function formatTime(timestamp: string): string {
  try {
    return new Date(timestamp).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return timestamp;
  }
}

export function SignalCard({
  signal,
  isExpanded,
  isFocused = false,
  onToggleExpand,
  events = [],
}: SignalCardProps) {
  return (
    <article
      className={`signal-card-v2 ${isExpanded ? "expanded" : ""} ${isFocused ? "focused" : ""}`}
      aria-label={`${signal.action} signal for ${signal.symbol} with opportunity score ${signal.opportunity_score.toFixed(0)}`}
      aria-expanded={isExpanded}
    >
      {/* Header Row */}
      <div className="signal-card-header-v2">
        <div className="signal-tier">
          <span role="img" aria-label={getTierLabel(signal.opportunity_tier)}>
            {getTierIcon(signal.opportunity_tier)}
          </span>
          <span className="opportunity-score">{signal.opportunity_score.toFixed(0)}</span>
        </div>
        <time className="signal-time-v2" dateTime={signal.timestamp}>
          {formatTime(signal.timestamp)}
        </time>
      </div>

      {/* Signal Info */}
      <div className="signal-info-v2">
        <span className={`signal-action-v2 ${getActionClass(signal.action)}`}>
          {signal.action === "BUY" ? "\uD83D\uDFE2" : signal.action === "SELL" ? "\uD83D\uDD34" : "\u26AA"}{" "}
          {signal.action}
        </span>
        <span className="signal-symbol-v2">{signal.symbol}</span>
        <span className="signal-confidence-v2">
          Confidence: {(signal.confidence * 100).toFixed(0)}%
        </span>
      </div>

      {/* Summary */}
      <p className="signal-summary-v2">
        Expected return: +{(signal.opportunity_factors.expected_return.value * 100).toFixed(1)}% |{" "}
        {signal.strategies_bullish}/{signal.strategies_analyzed} strategies bullish
      </p>

      {/* Expand Toggle */}
      <button
        onClick={onToggleExpand}
        className="signal-expand-toggle"
        aria-expanded={isExpanded}
        aria-controls={`signal-details-${signal.signal_id}`}
      >
        {isExpanded ? "\u25B2 Hide reasoning" : "\u25BC Show reasoning"}
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div id={`signal-details-${signal.signal_id}`} className="signal-details-v2">
          <ScoreBreakdown
            factors={signal.opportunity_factors}
            totalScore={signal.opportunity_score}
          />
          <ToolCallLog events={events} />
          <div className="signal-analysis">
            <div className="analysis-header">Analysis</div>
            <p>{signal.reasoning}</p>
          </div>
          {signal.strategy_breakdown.length > 0 && (
            <StrategyBreakdown strategies={signal.strategy_breakdown} />
          )}
        </div>
      )}
    </article>
  );
}
