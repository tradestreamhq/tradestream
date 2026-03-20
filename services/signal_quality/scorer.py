"""
Signal Quality Scorer — Phase 4.

Calculates a confidence score for each signal based on:
- Indicator agreement: how many indicators in the strategy agree on the direction
- Volume confirmation: whether volume supports the signal
- Trend alignment: whether the signal aligns with the broader trend
- Volatility context: whether current volatility is favorable

Each component is scored 0.0–1.0, then combined into a weighted composite
and mapped to a letter grade (A–F).
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Grade thresholds
GRADE_THRESHOLDS = [
    (0.80, "A"),
    (0.65, "B"),
    (0.50, "C"),
    (0.35, "D"),
]
DEFAULT_GRADE = "F"

# Component weights
INDICATOR_AGREEMENT_WEIGHT = 0.35
VOLUME_CONFIRMATION_WEIGHT = 0.25
TREND_ALIGNMENT_WEIGHT = 0.25
VOLATILITY_CONTEXT_WEIGHT = 0.15


@dataclass
class QualityScore:
    confidence: float
    indicator_agreement: float
    volume_confirmation: float
    trend_alignment: float
    volatility_context: float
    grade: str


def compute_grade(confidence: float) -> str:
    for threshold, grade in GRADE_THRESHOLDS:
        if confidence >= threshold:
            return grade
    return DEFAULT_GRADE


def score_signal(
    entry_conditions_met: int,
    total_entry_conditions: int,
    volume_above_average: bool,
    volume_ratio: float,
    trend_direction_matches: bool,
    trend_strength: float,
    volatility_percentile: float,
) -> QualityScore:
    """Score a signal based on its quality components.

    Args:
        entry_conditions_met: number of entry conditions that fired
        total_entry_conditions: total entry conditions in the strategy
        volume_above_average: whether current volume exceeds its moving average
        volume_ratio: current volume / average volume (e.g. 1.5 = 50% above average)
        trend_direction_matches: whether signal direction aligns with the broader trend
        trend_strength: strength of the trend (0.0-1.0, e.g. from ADX normalized)
        volatility_percentile: current volatility percentile (0.0-1.0, where 0.5 = median)
    """
    # Indicator agreement
    if total_entry_conditions > 0:
        indicator_agreement = entry_conditions_met / total_entry_conditions
    else:
        indicator_agreement = 0.5

    # Volume confirmation
    if volume_above_average:
        volume_confirmation = min(volume_ratio / 2.0, 1.0)
    else:
        volume_confirmation = max(0.0, volume_ratio / 2.0)

    # Trend alignment
    if trend_direction_matches:
        trend_alignment = 0.5 + (trend_strength * 0.5)
    else:
        trend_alignment = max(0.0, 0.3 - (trend_strength * 0.3))

    # Volatility context: moderate volatility (0.3-0.7) is ideal
    if 0.3 <= volatility_percentile <= 0.7:
        volatility_context = 1.0 - abs(volatility_percentile - 0.5) * 2
    elif volatility_percentile > 0.7:
        volatility_context = max(0.0, 1.0 - (volatility_percentile - 0.7) * 3)
    else:
        volatility_context = max(0.0, volatility_percentile / 0.3)

    confidence = (
        indicator_agreement * INDICATOR_AGREEMENT_WEIGHT
        + volume_confirmation * VOLUME_CONFIRMATION_WEIGHT
        + trend_alignment * TREND_ALIGNMENT_WEIGHT
        + volatility_context * VOLATILITY_CONTEXT_WEIGHT
    )

    grade = compute_grade(confidence)

    return QualityScore(
        confidence=round(confidence, 4),
        indicator_agreement=round(indicator_agreement, 4),
        volume_confirmation=round(volume_confirmation, 4),
        trend_alignment=round(trend_alignment, 4),
        volatility_context=round(volatility_context, 4),
        grade=grade,
    )


async def store_quality_score(
    db_pool, signal_id: str, strategy_name: str, symbol: str, quality: QualityScore
) -> str:
    """Persist a quality score to the database."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO signal_quality_scores
               (signal_id, strategy_name, symbol, confidence,
                indicator_agreement, volume_confirmation,
                trend_alignment, volatility_context, quality_grade)
               VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9)
               RETURNING id""",
            signal_id,
            strategy_name,
            symbol,
            quality.confidence,
            quality.indicator_agreement,
            quality.volume_confirmation,
            quality.trend_alignment,
            quality.volatility_context,
            quality.grade,
        )
        return str(row["id"])
