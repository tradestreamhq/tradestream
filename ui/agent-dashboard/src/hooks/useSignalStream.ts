import { useMemo, useRef, useEffect, useCallback } from "react";
import type { AgentEvent, Signal, SignalFilters, OpportunityTier, SignalAction, OpportunityFactors } from "../types";

function computeTier(score: number): OpportunityTier {
  if (score >= 80) return "HOT";
  if (score >= 60) return "GOOD";
  return "NEUTRAL";
}

function eventToSignal(event: AgentEvent): Signal | null {
  if (event.event_type !== "signal" || event.score == null) return null;

  const score = event.score * 100;
  const tier = event.tier as OpportunityTier | null;
  const action: SignalAction = event.decision_type === "sell" ? "SELL"
    : event.decision_type === "hold" ? "HOLD" : "BUY";

  const factors: OpportunityFactors = {
    confidence: { value: event.score, contribution: event.score * 25 },
    expected_return: { value: Math.max(0, event.score * 0.05), contribution: event.score * 30 },
    consensus: { value: event.score * 0.8, contribution: event.score * 20 },
    volatility: { value: 0.02 + Math.random() * 0.03, contribution: event.score * 15 },
    freshness: { value: 1, contribution: event.score * 10 },
  };

  return {
    signal_id: event.signal_id || event.id,
    symbol: event.agent_name?.includes("/") ? event.agent_name : "ETH/USD",
    action,
    confidence: event.score,
    opportunity_score: score,
    opportunity_tier: tier ? (tier.toUpperCase() as OpportunityTier) : computeTier(score),
    opportunity_factors: factors,
    reasoning: event.reasoning || "",
    timestamp: event.created_at,
    strategies_bullish: Math.round(event.score * 5),
    strategies_analyzed: 5,
    strategy_breakdown: [],
  };
}

interface UseSignalStreamOptions {
  events: AgentEvent[];
  filters?: SignalFilters;
  maxSignals?: number;
}

export function useSignalStream({ events, filters = {}, maxSignals = 100 }: UseSignalStreamOptions) {
  const prevCountRef = useRef(0);

  const signals = useMemo(() => {
    let result: Signal[] = [];
    for (const event of events) {
      const signal = eventToSignal(event);
      if (signal) result.push(signal);
      if (result.length >= maxSignals) break;
    }

    if (filters.symbols?.length) {
      result = result.filter((s) => filters.symbols!.includes(s.symbol));
    }
    if (filters.actions?.length) {
      result = result.filter((s) => filters.actions!.includes(s.action));
    }
    if (filters.minConfidence != null) {
      result = result.filter((s) => s.confidence >= filters.minConfidence!);
    }
    if (filters.minOpportunityScore != null) {
      result = result.filter((s) => s.opportunity_score >= filters.minOpportunityScore!);
    }

    return result.sort((a, b) => b.opportunity_score - a.opportunity_score);
  }, [events, filters, maxSignals]);

  const hasNewSignal = signals.length > prevCountRef.current;
  const latestSignal = hasNewSignal ? signals[0] : null;

  useEffect(() => {
    prevCountRef.current = signals.length;
  }, [signals.length]);

  return { signals, hasNewSignal, latestSignal };
}
