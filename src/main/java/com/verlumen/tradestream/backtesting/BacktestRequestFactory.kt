package com.verlumen.tradestream.backtesting

import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.backtesting.BacktestRequest

/**
 * Interface for creating BacktestRequest objects.
 */
interface BacktestRequestFactory {
    /**
     * Creates a BacktestRequest based on the provided candles and strategy.
     *
     * @param candles The list of historical price candles.
     * @param strategy The trading strategy to be backtested.
     * @return A configured BacktestRequest object.
     */
    fun create(candles: List<Candle>, strategy: Strategy): BacktestRequest
}
