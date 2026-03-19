"""Tests for the Opportunity Scoring Engine."""

import json
import time
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from services.opportunity_scoring.aggregator import (
    aggregate_signals,
    calculate_expected_return,
    compute_consensus,
    rank_opportunities,
)
from services.opportunity_scoring.app import create_app
from services.opportunity_scoring.lifecycle import OpportunityTracker
from services.opportunity_scoring.models import (
    ContributingSignal,
    MarketRegime,
    OpportunityStatus,
    OpportunityTier,
    ScoredOpportunity,
)
from services.opportunity_scoring.scoring import (
    DEFAULTS,
    apply_sharpe_adjustment,
    assign_tier,
    calculate_opportunity_score,
    detect_regime,
    get_regime_caps,
)


# ─── Scoring Tests ────────────────────────────────────────────


class TestRegimeCaps:
    def test_normal_caps(self):
        caps = get_regime_caps("normal")
        assert caps.max_return == 0.05
        assert caps.max_volatility == 0.03

    def test_high_volatility_caps(self):
        caps = get_regime_caps("high_volatility")
        assert caps.max_return == 0.08
        assert caps.max_volatility == 0.05

    def test_extreme_caps(self):
        caps = get_regime_caps("extreme")
        assert caps.max_return == 0.15
        assert caps.max_volatility == 0.10

    def test_unknown_defaults_to_normal(self):
        caps = get_regime_caps("unknown")
        assert caps.max_return == 0.05


class TestSharpeAdjustment:
    def test_zero_stddev_returns_raw(self):
        assert apply_sharpe_adjustment(0.03, 0.0) == 0.03

    def test_negative_stddev_returns_raw(self):
        assert apply_sharpe_adjustment(0.03, -1.0) == 0.03

    def test_equal_return_and_stddev(self):
        # Sharpe = 1.0, adjustment = 1.0/2.0 = 0.5, multiplier = 0.75
        result = apply_sharpe_adjustment(0.03, 0.03)
        assert result == pytest.approx(0.03 * 0.75, abs=1e-6)

    def test_high_sharpe_capped(self):
        # Sharpe = 3.0, capped to 2.0, adjustment = 2.0/2.0 = 1.0, multiplier = 1.0
        result = apply_sharpe_adjustment(0.03, 0.01)
        assert result == pytest.approx(0.03, abs=1e-6)

    def test_low_sharpe_penalized(self):
        # Sharpe = 0.5, adjustment = 0.5/2.0 = 0.25, multiplier = 0.625
        result = apply_sharpe_adjustment(0.03, 0.06)
        assert result == pytest.approx(0.03 * 0.625, abs=1e-6)

    def test_consistent_beats_volatile(self):
        """Strategy A (low stddev) should score higher than B (high stddev)."""
        consistent = apply_sharpe_adjustment(0.03, 0.01)
        volatile = apply_sharpe_adjustment(0.03, 0.06)
        assert consistent > volatile


class TestDetectRegime:
    def test_normal(self):
        assert detect_regime(0.5) == "normal"
        assert detect_regime(0.79) == "normal"

    def test_high_volatility(self):
        assert detect_regime(0.80) == "high_volatility"
        assert detect_regime(0.94) == "high_volatility"

    def test_extreme(self):
        assert detect_regime(0.95) == "extreme"
        assert detect_regime(1.0) == "extreme"


class TestAssignTier:
    def test_hot(self):
        assert assign_tier(80) == "HOT"
        assert assign_tier(100) == "HOT"

    def test_good(self):
        assert assign_tier(60) == "GOOD"
        assert assign_tier(79.9) == "GOOD"

    def test_neutral(self):
        assert assign_tier(40) == "NEUTRAL"
        assert assign_tier(59.9) == "NEUTRAL"

    def test_low(self):
        assert assign_tier(0) == "LOW"
        assert assign_tier(39.9) == "LOW"


class TestCalculateOpportunityScore:
    def test_perfect_score(self):
        score, breakdown = calculate_opportunity_score(
            confidence=1.0,
            expected_return=0.05,
            return_stddev=0.0,
            consensus_pct=1.0,
            volatility=0.03,
            minutes_ago=0,
            market_regime="normal",
        )
        assert score == 100.0

    def test_zero_score(self):
        score, breakdown = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=60,
            market_regime="normal",
        )
        assert score == 0.0

    def test_deterministic(self):
        """Same inputs must always produce the same score."""
        args = dict(
            confidence=0.82,
            expected_return=0.032,
            return_stddev=0.015,
            consensus_pct=0.80,
            volatility=0.021,
            minutes_ago=0,
            market_regime="normal",
        )
        score1, _ = calculate_opportunity_score(**args)
        score2, _ = calculate_opportunity_score(**args)
        assert score1 == score2

    def test_confidence_weight(self):
        score, breakdown = calculate_opportunity_score(
            confidence=1.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=60,
            market_regime="normal",
        )
        assert score == 25.0
        assert breakdown.confidence_contribution == 25.0

    def test_return_weight(self):
        score, breakdown = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.05,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=60,
            market_regime="normal",
        )
        assert score == 30.0
        assert breakdown.expected_return_contribution == 30.0

    def test_consensus_weight(self):
        score, _ = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=1.0,
            volatility=0.0,
            minutes_ago=60,
            market_regime="normal",
        )
        assert score == 20.0

    def test_volatility_weight(self):
        score, _ = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.03,
            minutes_ago=60,
            market_regime="normal",
        )
        assert score == 15.0

    def test_freshness_weight(self):
        score, _ = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=0,
            market_regime="normal",
        )
        assert score == 10.0

    def test_freshness_decay(self):
        score_fresh, _ = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=0,
        )
        score_30, _ = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=30,
        )
        score_60, _ = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.0,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=60,
        )
        assert score_fresh == 10.0
        assert score_30 == 5.0
        assert score_60 == 0.0

    def test_regime_affects_return_cap(self):
        """In extreme regime, same return gets a lower score (wider cap)."""
        _, breakdown_normal = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.05,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=60,
            market_regime="normal",
        )
        _, breakdown_extreme = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.05,
            return_stddev=0.0,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=60,
            market_regime="extreme",
        )
        assert (
            breakdown_normal.expected_return_contribution
            > breakdown_extreme.expected_return_contribution
        )

    def test_sharpe_adjustment_affects_score(self):
        """High stddev should lower the score vs low stddev."""
        score_consistent, _ = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.03,
            return_stddev=0.01,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=60,
        )
        score_volatile, _ = calculate_opportunity_score(
            confidence=0.0,
            expected_return=0.03,
            return_stddev=0.06,
            consensus_pct=0.0,
            volatility=0.0,
            minutes_ago=60,
        )
        assert score_consistent > score_volatile

    def test_breakdown_populated(self):
        _, breakdown = calculate_opportunity_score(
            confidence=0.82,
            expected_return=0.032,
            return_stddev=0.015,
            consensus_pct=0.80,
            volatility=0.021,
            minutes_ago=0,
            market_regime="normal",
        )
        assert breakdown.confidence_value == 0.82
        assert breakdown.expected_return_value == 0.032
        assert breakdown.expected_return_stddev == 0.015
        assert breakdown.consensus_value == 0.80
        assert breakdown.volatility_value == 0.021
        assert breakdown.freshness_value == 0
        assert breakdown.market_regime == "normal"
        assert breakdown.risk_adjusted_return > 0


# ─── Consensus Tests ──────────────────────────────────────────


class TestConsensus:
    def test_unanimous_buy(self):
        signals = [
            ContributingSignal("tech", "s1", "BUY", 0.9),
            ContributingSignal("sentiment", "s2", "BUY", 0.8),
        ]
        direction, pct, agreeing, total = compute_consensus(signals)
        assert direction == "BUY"
        assert pct == 1.0
        assert agreeing == 2
        assert total == 2

    def test_split_signals(self):
        signals = [
            ContributingSignal("tech", "s1", "BUY", 0.9),
            ContributingSignal("sentiment", "s2", "SELL", 0.8),
        ]
        direction, pct, agreeing, total = compute_consensus(signals)
        # BUY wins by confidence weight
        assert direction == "BUY"
        assert pct == 0.5
        assert agreeing == 1
        assert total == 2

    def test_majority_sell(self):
        signals = [
            ContributingSignal("tech", "s1", "SELL", 0.9),
            ContributingSignal("sentiment", "s2", "SELL", 0.7),
            ContributingSignal("prediction", "s3", "BUY", 0.6),
        ]
        direction, pct, _, _ = compute_consensus(signals)
        assert direction == "SELL"
        assert pct == pytest.approx(2 / 3)

    def test_empty_signals(self):
        direction, pct, _, _ = compute_consensus([])
        assert direction == "HOLD"
        assert pct == 0.0

    def test_all_hold_returns_hold(self):
        signals = [
            ContributingSignal("tech", "s1", "HOLD", 0.9),
        ]
        direction, pct, _, _ = compute_consensus(signals)
        assert direction == "HOLD"


class TestExpectedReturn:
    def test_weighted_by_confidence(self):
        signals = [
            ContributingSignal(
                "tech", "s1", "BUY", 0.8, expected_return=0.04, return_stddev=0.01
            ),
            ContributingSignal(
                "sentiment", "s2", "BUY", 0.2, expected_return=0.02, return_stddev=0.02
            ),
        ]
        ret, std = calculate_expected_return(signals, "BUY")
        # (0.04*0.8 + 0.02*0.2) / (0.8+0.2) = 0.036
        assert ret == pytest.approx(0.036, abs=1e-4)

    def test_ignores_disagreeing_signals(self):
        signals = [
            ContributingSignal("tech", "s1", "BUY", 0.9, expected_return=0.03),
            ContributingSignal("sentiment", "s2", "SELL", 0.8, expected_return=0.05),
        ]
        ret, _ = calculate_expected_return(signals, "BUY")
        assert ret == pytest.approx(0.03, abs=1e-4)

    def test_defaults_when_no_data(self):
        ret, std = calculate_expected_return([], "BUY")
        assert ret == DEFAULTS["expected_return"]
        assert std == DEFAULTS["return_stddev"]


# ─── Aggregation Tests ────────────────────────────────────────


class TestAggregateSignals:
    def test_basic_aggregation(self):
        signals = [
            ContributingSignal("tech", "s1", "BUY", 0.9, "RSI_REVERSAL", 0.03, 0.01),
            ContributingSignal(
                "sentiment", "s2", "BUY", 0.7, "NEWS_SENTIMENT", 0.02, 0.005
            ),
        ]
        opp = aggregate_signals("BTC/USD", signals, volatility=0.02)
        assert opp is not None
        assert opp.symbol == "BTC/USD"
        assert opp.direction == "BUY"
        assert opp.opportunity_score > 0
        assert opp.tier in ("HOT", "GOOD", "NEUTRAL", "LOW")
        assert opp.strategies_agreeing == 2
        assert opp.top_strategy == "RSI_REVERSAL"

    def test_empty_signals_returns_none(self):
        assert aggregate_signals("BTC/USD", []) is None

    def test_hold_signals_return_none(self):
        signals = [ContributingSignal("tech", "s1", "HOLD", 0.9)]
        assert aggregate_signals("BTC/USD", signals) is None

    def test_consensus_boosts_score(self):
        """More agreeing signals should produce a higher score."""
        solo = [ContributingSignal("tech", "s1", "BUY", 0.8, expected_return=0.03)]
        consensus = [
            ContributingSignal("tech", "s1", "BUY", 0.8, expected_return=0.03),
            ContributingSignal("sentiment", "s2", "BUY", 0.8, expected_return=0.03),
            ContributingSignal("prediction", "s3", "BUY", 0.8, expected_return=0.03),
        ]
        opp_solo = aggregate_signals("BTC/USD", solo)
        opp_consensus = aggregate_signals("BTC/USD", consensus)
        assert opp_consensus.opportunity_score >= opp_solo.opportunity_score

    def test_extreme_regime_detection(self):
        signals = [ContributingSignal("tech", "s1", "BUY", 0.9, expected_return=0.03)]
        opp = aggregate_signals("BTC/USD", signals, volatility_percentile=0.96)
        assert opp.market_regime == "extreme"

    def test_score_cached_at_creation(self):
        """Score should not change over time (freshness locked at 0)."""
        signals = [ContributingSignal("tech", "s1", "BUY", 0.9, expected_return=0.03)]
        opp = aggregate_signals("BTC/USD", signals)
        score_at_creation = opp.opportunity_score
        # Even if display age changes, the score is locked
        assert opp.score_breakdown.freshness_value == 0
        assert opp.opportunity_score == score_at_creation


# ─── Ranking Tests ────────────────────────────────────────────


class TestRankOpportunities:
    def _make_opp(self, score, tier="GOOD", symbol="BTC/USD", minutes_old=0):
        _, breakdown = calculate_opportunity_score(
            confidence=0.5,
            expected_return=0.02,
            return_stddev=0.01,
            consensus_pct=0.5,
            volatility=0.01,
            minutes_ago=0,
        )
        opp = ScoredOpportunity(
            opportunity_id=f"opp-{score}",
            symbol=symbol,
            direction="BUY",
            opportunity_score=score,
            tier=tier,
            score_breakdown=breakdown,
            contributing_signals=[],
            strategies_analyzed=1,
            strategies_agreeing=1,
            top_strategy=None,
            market_regime="normal",
            scored_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_old),
        )
        return opp

    def test_sorted_by_score_descending(self):
        opps = [self._make_opp(50), self._make_opp(80), self._make_opp(65)]
        ranked = rank_opportunities(opps)
        scores = [o.opportunity_score for o in ranked]
        assert scores == [80, 65, 50]

    def test_min_score_filter(self):
        opps = [self._make_opp(30), self._make_opp(60), self._make_opp(90)]
        ranked = rank_opportunities(opps, min_score=50)
        assert len(ranked) == 2
        assert all(o.opportunity_score >= 50 for o in ranked)

    def test_min_tier_filter(self):
        opps = [
            self._make_opp(30, "LOW"),
            self._make_opp(50, "NEUTRAL"),
            self._make_opp(70, "GOOD"),
            self._make_opp(90, "HOT"),
        ]
        ranked = rank_opportunities(opps, min_tier="GOOD")
        assert len(ranked) == 2
        assert all(o.tier in ("GOOD", "HOT") for o in ranked)

    def test_exclude_stale(self):
        opps = [self._make_opp(80, minutes_old=0), self._make_opp(90, minutes_old=61)]
        ranked = rank_opportunities(opps, exclude_stale=True)
        assert len(ranked) == 1
        assert ranked[0].opportunity_score == 80

    def test_include_stale(self):
        opps = [self._make_opp(80, minutes_old=0), self._make_opp(90, minutes_old=61)]
        ranked = rank_opportunities(opps, exclude_stale=False)
        assert len(ranked) == 2


# ─── Lifecycle Tests ──────────────────────────────────────────


class TestOpportunityTracker:
    def _make_opp(self, opp_id="opp-1"):
        _, breakdown = calculate_opportunity_score(
            confidence=0.8,
            expected_return=0.03,
            return_stddev=0.01,
            consensus_pct=0.8,
            volatility=0.02,
            minutes_ago=0,
        )
        return ScoredOpportunity(
            opportunity_id=opp_id,
            symbol="BTC/USD",
            direction="BUY",
            opportunity_score=85.0,
            tier="HOT",
            score_breakdown=breakdown,
            contributing_signals=[],
            strategies_analyzed=3,
            strategies_agreeing=2,
            top_strategy="RSI",
            market_regime="normal",
        )

    def test_track_and_get(self):
        tracker = OpportunityTracker()
        opp = self._make_opp()
        tracker.track(opp)
        assert tracker.get("opp-1") is opp

    def test_get_not_found(self):
        tracker = OpportunityTracker()
        assert tracker.get("nonexistent") is None

    def test_lifecycle_scored_to_signaled(self):
        tracker = OpportunityTracker()
        opp = self._make_opp()
        tracker.track(opp)
        assert tracker.mark_signaled("opp-1") is True
        assert opp.status == "signaled"

    def test_lifecycle_signaled_to_entered(self):
        tracker = OpportunityTracker()
        opp = self._make_opp()
        tracker.track(opp)
        tracker.mark_signaled("opp-1")
        assert tracker.mark_entered("opp-1") is True
        assert opp.status == "entered"
        assert opp.entered_at is not None

    def test_lifecycle_entered_to_closed(self):
        tracker = OpportunityTracker()
        opp = self._make_opp()
        tracker.track(opp)
        tracker.mark_signaled("opp-1")
        tracker.mark_entered("opp-1")
        assert tracker.mark_closed("opp-1", outcome_return=0.025) is True
        assert opp.status == "closed"
        assert opp.outcome_return == 0.025

    def test_invalid_transition_rejected(self):
        tracker = OpportunityTracker()
        opp = self._make_opp()
        tracker.track(opp)
        # Can't go directly to closed from scored
        assert tracker.mark_closed("opp-1") is False

    def test_expire_stale(self):
        tracker = OpportunityTracker()
        opp = self._make_opp()
        opp.scored_at = datetime.now(timezone.utc) - timedelta(minutes=61)
        tracker.track(opp)
        count = tracker.expire_stale()
        assert count == 1
        assert opp.status == "expired"

    def test_list_active_excludes_closed(self):
        tracker = OpportunityTracker()
        opp1 = self._make_opp("opp-1")
        opp2 = self._make_opp("opp-2")
        tracker.track(opp1)
        tracker.track(opp2)
        tracker.mark_signaled("opp1-1")  # This won't work, wrong ID
        tracker.mark_expired("opp-2")
        active = tracker.list_active()
        assert len(active) == 1

    def test_stats(self):
        tracker = OpportunityTracker()
        tracker.track(self._make_opp("opp-1"))
        tracker.track(self._make_opp("opp-2"))
        stats = tracker.get_stats()
        assert stats["total"] == 2
        assert stats["avg_score"] == 85.0


# ─── API Tests ────────────────────────────────────────────────


@pytest.fixture
def tracker():
    return OpportunityTracker()


@pytest.fixture
def client(tracker):
    app = create_app(tracker)
    return TestClient(app, raise_server_exceptions=False)


class TestOpportunityAPI:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_score_signals(self, client):
        resp = client.post(
            "/score",
            json={
                "symbol": "BTC/USD",
                "signals": [
                    {
                        "source": "technical",
                        "signal_id": "s1",
                        "direction": "BUY",
                        "confidence": 0.85,
                        "strategy_name": "RSI_REVERSAL",
                        "expected_return": 0.032,
                        "return_stddev": 0.015,
                    },
                    {
                        "source": "sentiment",
                        "signal_id": "s2",
                        "direction": "BUY",
                        "confidence": 0.70,
                        "strategy_name": "NEWS_SENTIMENT",
                        "expected_return": 0.025,
                        "return_stddev": 0.01,
                    },
                ],
                "volatility": 0.021,
                "volatility_percentile": 0.65,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["type"] == "opportunity"
        attrs = body["data"]["attributes"]
        assert attrs["symbol"] == "BTC/USD"
        assert attrs["direction"] == "BUY"
        assert attrs["opportunity_score"] > 0
        assert attrs["tier"] in ("HOT", "GOOD", "NEUTRAL", "LOW")
        assert "score_breakdown" in attrs

    def test_score_signals_no_symbol(self, client):
        resp = client.post("/score", json={"signals": [{"direction": "BUY"}]})
        assert resp.status_code == 422

    def test_score_signals_empty(self, client):
        resp = client.post("/score", json={"symbol": "BTC/USD", "signals": []})
        assert resp.status_code == 422

    def test_list_opportunities(self, client, tracker):
        # Score some opportunities first
        signals = [
            ContributingSignal("tech", "s1", "BUY", 0.9, "RSI", 0.03, 0.01),
        ]
        opp = aggregate_signals("BTC/USD", signals, volatility=0.02)
        tracker.track(opp)

        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1

    def test_list_with_min_score(self, client, tracker):
        signals = [ContributingSignal("tech", "s1", "BUY", 0.3, expected_return=0.005)]
        opp = aggregate_signals("BTC/USD", signals, volatility=0.005)
        tracker.track(opp)

        resp = client.get("/?min_score=80")
        body = resp.json()
        # Low confidence signal should be filtered out
        assert body["meta"]["total"] == 0

    def test_get_opportunity(self, client, tracker):
        signals = [ContributingSignal("tech", "s1", "BUY", 0.9, "RSI", 0.03)]
        opp = aggregate_signals("BTC/USD", signals)
        tracker.track(opp)

        resp = client.get(f"/{opp.opportunity_id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == opp.opportunity_id

    def test_get_opportunity_not_found(self, client):
        resp = client.get("/nonexistent-id")
        assert resp.status_code == 404

    def test_update_status_lifecycle(self, client, tracker):
        signals = [ContributingSignal("tech", "s1", "BUY", 0.9, "RSI", 0.03)]
        opp = aggregate_signals("BTC/USD", signals)
        tracker.track(opp)
        oid = opp.opportunity_id

        # scored → signaled
        resp = client.patch(f"/{oid}/status", json={"status": "signaled"})
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["status"] == "signaled"

        # signaled → entered
        resp = client.patch(f"/{oid}/status", json={"status": "entered"})
        assert resp.status_code == 200

        # entered → closed
        resp = client.patch(
            f"/{oid}/status",
            json={"status": "closed", "outcome_return": 0.025},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["status"] == "closed"

    def test_update_status_invalid_transition(self, client, tracker):
        signals = [ContributingSignal("tech", "s1", "BUY", 0.9)]
        opp = aggregate_signals("BTC/USD", signals)
        tracker.track(opp)

        # Can't go directly from scored to closed
        resp = client.patch(f"/{opp.opportunity_id}/status", json={"status": "closed"})
        assert resp.status_code == 422

    def test_stats(self, client, tracker):
        signals = [ContributingSignal("tech", "s1", "BUY", 0.9, "RSI", 0.03)]
        opp = aggregate_signals("BTC/USD", signals)
        tracker.track(opp)

        resp = client.get("/stats/summary")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["total"] == 1

    def test_hold_consensus_returns_no_opportunity(self, client):
        resp = client.post(
            "/score",
            json={
                "symbol": "BTC/USD",
                "signals": [
                    {
                        "source": "tech",
                        "signal_id": "s1",
                        "direction": "HOLD",
                        "confidence": 0.9,
                    },
                ],
            },
        )
        assert resp.status_code == 200
        assert (
            "No actionable opportunity" in resp.json()["data"]["attributes"]["message"]
        )


# ─── Model Tests ──────────────────────────────────────────────


class TestScoredOpportunityModel:
    def test_to_dict(self):
        _, breakdown = calculate_opportunity_score(
            confidence=0.8,
            expected_return=0.03,
            return_stddev=0.01,
            consensus_pct=0.8,
            volatility=0.02,
            minutes_ago=0,
        )
        signals = [ContributingSignal("tech", "s1", "BUY", 0.9, "RSI")]
        opp = ScoredOpportunity(
            opportunity_id="test-id",
            symbol="BTC/USD",
            direction="BUY",
            opportunity_score=85.0,
            tier="HOT",
            score_breakdown=breakdown,
            contributing_signals=signals,
            strategies_analyzed=3,
            strategies_agreeing=2,
            top_strategy="RSI",
            market_regime="normal",
        )
        d = opp.to_dict()
        assert d["opportunity_id"] == "test-id"
        assert d["symbol"] == "BTC/USD"
        assert d["score_breakdown"]["confidence"]["value"] == 0.8
        assert d["score_breakdown"]["freshness"]["cached"] is True
        assert len(d["contributing_signals"]) == 1
        assert d["contributing_signals"][0]["source"] == "tech"

    def test_is_stale(self):
        _, breakdown = calculate_opportunity_score(
            confidence=0.5,
            expected_return=0.01,
            return_stddev=0.0,
            consensus_pct=0.5,
            volatility=0.01,
            minutes_ago=0,
        )
        opp = ScoredOpportunity(
            opportunity_id="stale",
            symbol="ETH/USD",
            direction="BUY",
            opportunity_score=50.0,
            tier="NEUTRAL",
            score_breakdown=breakdown,
            contributing_signals=[],
            strategies_analyzed=1,
            strategies_agreeing=1,
            top_strategy=None,
            market_regime="normal",
            scored_at=datetime.now(timezone.utc) - timedelta(minutes=61),
        )
        assert opp.is_stale is True
