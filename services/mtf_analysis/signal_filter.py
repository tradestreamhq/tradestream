"""
Integration with the execution engine as an optional signal filter.

Provides a filter function that can be wired into the execution pipeline
to reject signals that lack multi-timeframe confluence.
"""

from typing import Any, Dict, Optional

from services.mtf_analysis.analyzer import MultiTimeframeAnalyzer, Signal


class MTFSignalFilter:
    """Filter trade signals based on multi-timeframe confluence.

    Rejects signals whose direction conflicts with the dominant
    multi-timeframe trend or whose confluence score is too weak.
    """

    def __init__(
        self,
        analyzer: MultiTimeframeAnalyzer,
        min_confluence: float = 0.3,
        min_agreeing: int = 2,
    ):
        self._analyzer = analyzer
        self._min_confluence = min_confluence
        self._min_agreeing = min_agreeing

    def should_execute(self, pair: str, signal_direction: str) -> Dict[str, Any]:
        """Decide whether a signal should be executed.

        Args:
            pair: Trading pair (e.g. BTC/USD).
            signal_direction: "BUY" or "SELL".

        Returns:
            Dict with "allowed" (bool), "reason" (str), and "confluence" details.
        """
        confluence = self._analyzer.get_confluence(pair)

        # Map signal direction to expected MTF signal.
        expected = Signal.BULLISH if signal_direction.upper() == "BUY" else Signal.BEARISH

        allowed = True
        reason = "Signal passes MTF filter"

        # Check score magnitude.
        if abs(confluence.score) < self._min_confluence:
            allowed = False
            reason = (
                f"Confluence score {confluence.score} below "
                f"threshold {self._min_confluence}"
            )
        # Check direction agreement.
        elif confluence.signal != Signal.NEUTRAL and confluence.signal != expected:
            allowed = False
            reason = (
                f"Signal direction {signal_direction} conflicts with "
                f"MTF trend {confluence.signal.value}"
            )
        # Check minimum agreeing timeframes.
        elif len(confluence.agreeing_timeframes) < self._min_agreeing:
            allowed = False
            reason = (
                f"Only {len(confluence.agreeing_timeframes)} agreeing timeframes, "
                f"need {self._min_agreeing}"
            )

        return {
            "allowed": allowed,
            "reason": reason,
            "confluence_score": confluence.score,
            "confluence_signal": confluence.signal.value,
            "agreeing_timeframes": confluence.agreeing_timeframes,
        }
