package com.verlumen.tradestream.backtesting

/** Compares multiple trading strategies by backtesting them on the same market data. */
interface StrategyComparator {
    /**
     * Runs backtests for all strategies in the request on the same candle data,
     * ranks them by the specified metric, and computes pairwise return correlations.
     *
     * @param request The comparison request containing candles, strategies, and ranking metric
     * @return Comparison result with ranked entries and correlation analysis
     */
    fun compare(request: StrategyComparisonRequest): StrategyComparisonResult
}
