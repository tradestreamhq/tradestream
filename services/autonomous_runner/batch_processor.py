"""Parallel batch processor with semaphore-limited concurrency.

Processes symbols in batches with controlled parallelism, handles partial
failures, and generates degraded signals when some data sources fail.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class BatchConfig:
    """Batch processing configuration."""

    max_concurrent_symbols: int = 10
    thread_pool_size: int = 20
    batch_size: int = 10
    inter_batch_delay_ms: int = 1000


@dataclass
class FailedSymbol:
    """Record of a failed symbol processing."""

    symbol: str
    error: str
    error_type: str
    retries_attempted: int = 0


@dataclass
class PartialSignal:
    """A signal generated with incomplete data."""

    signal: dict
    missing_data: list = field(default_factory=list)
    confidence_penalty: float = 0.0


@dataclass
class BatchResult:
    """Result of processing a batch of symbols."""

    successful: list = field(default_factory=list)
    failed: list = field(default_factory=list)
    partial: list = field(default_factory=list)
    batch_latency_ms: int = 0

    @property
    def success_rate(self) -> float:
        total = len(self.successful) + len(self.failed) + len(self.partial)
        return (len(self.successful) + len(self.partial)) / total if total > 0 else 0.0

    @property
    def total_processed(self) -> int:
        return len(self.successful) + len(self.failed) + len(self.partial)


# Confidence penalties for missing data sources
DEGRADATION_PENALTIES = {
    "strategies": 0.20,
    "market_context": 0.10,
    "volatility": 0.05,
    "sentiment": 0.05,
    "prediction_market": 0.05,
}


class PartialDataError(Exception):
    """Raised when some data sources fail but enough data exists for a signal."""

    def __init__(self, available_data: dict, missing_tools: list):
        self.available_data = available_data
        self.missing_tools = missing_tools
        self.confidence_penalty = sum(
            DEGRADATION_PENALTIES.get(t, 0.05) for t in missing_tools
        )
        super().__init__(f"Partial data: missing {missing_tools}")


class BatchProcessor:
    """Process symbols in parallel batches with concurrency control.

    Uses asyncio.Semaphore to limit concurrent symbol processing and
    ThreadPoolExecutor for blocking I/O operations.
    """

    def __init__(self, config: Optional[BatchConfig] = None):
        self.config = config or BatchConfig()
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_symbols)
        self._executor = ThreadPoolExecutor(max_workers=self.config.thread_pool_size)

    async def process_batch(
        self,
        symbols: list,
        process_fn: Callable,
    ) -> BatchResult:
        """Process a batch of symbols with controlled parallelism.

        Args:
            symbols: List of symbol strings to process.
            process_fn: Callable(symbol) -> dict that processes one symbol.
                Should raise PartialDataError for degraded signals.

        Returns:
            BatchResult with successful, failed, and partial results.
        """
        start = time.time()
        result = BatchResult()

        # Process in batches
        for i in range(0, len(symbols), self.config.batch_size):
            batch = symbols[i : i + self.config.batch_size]
            tasks = [self._process_with_limit(sym, process_fn) for sym in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for symbol, res in zip(batch, batch_results):
                if isinstance(res, Exception):
                    result.failed.append(
                        FailedSymbol(
                            symbol=symbol,
                            error=str(res),
                            error_type=type(res).__name__,
                        )
                    )
                elif isinstance(res, PartialSignal):
                    result.partial.append(res)
                elif res is not None:
                    result.successful.append(res)

            # Inter-batch delay
            if (
                i + self.config.batch_size < len(symbols)
                and self.config.inter_batch_delay_ms > 0
            ):
                await asyncio.sleep(self.config.inter_batch_delay_ms / 1000.0)

        result.batch_latency_ms = int((time.time() - start) * 1000)

        if result.success_rate < 0.5 and result.total_processed > 0:
            logger.error(
                "Batch failure rate critical: %.1f%%",
                (1 - result.success_rate) * 100,
            )

        return result

    async def _process_with_limit(self, symbol: str, process_fn: Callable):
        """Process a single symbol with semaphore limiting."""
        async with self._semaphore:
            loop = asyncio.get_event_loop()
            try:
                return await loop.run_in_executor(self._executor, process_fn, symbol)
            except PartialDataError as e:
                return PartialSignal(
                    signal=e.available_data,
                    missing_data=e.missing_tools,
                    confidence_penalty=e.confidence_penalty,
                )

    def shutdown(self):
        """Shut down the thread pool."""
        self._executor.shutdown(wait=False)


def generate_degraded_signal(
    symbol: str,
    available_data: dict,
    missing_tools: list,
) -> dict:
    """Generate a signal with incomplete data, applying confidence penalties.

    Args:
        symbol: Trading symbol.
        available_data: Data that was successfully retrieved.
        missing_tools: List of data source names that failed.

    Returns:
        Signal dict with reduced confidence and degraded flag.
    """
    total_penalty = sum(DEGRADATION_PENALTIES.get(tool, 0.05) for tool in missing_tools)

    # Determine action from available data
    action = "HOLD"
    base_confidence = 0.70

    strategies = available_data.get("strategies")
    if strategies and isinstance(strategies, list):
        buy = sum(1 for s in strategies if s.get("signal") == "BUY")
        sell = sum(1 for s in strategies if s.get("signal") == "SELL")
        if buy > sell:
            action = "BUY"
        elif sell > buy:
            action = "SELL"

    confidence = max(0.30, base_confidence - total_penalty)

    return {
        "symbol": symbol,
        "action": action,
        "confidence": round(confidence, 3),
        "reasoning": f"Degraded signal: missing {', '.join(missing_tools)}",
        "is_degraded": True,
        "missing_data": missing_tools,
        "confidence_penalty": round(total_penalty, 3),
    }
