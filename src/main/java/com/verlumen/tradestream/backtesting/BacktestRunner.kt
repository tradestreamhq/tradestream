package com.verlumen.tradestream.backtesting

import java.io.Serializable

/** Interface for running backtests on trading strategies. */
interface BacktestRunner : Serializable {
    /**
     * Runs a backtest for the given strategy over the provided bar series.
     *
     * @param request Parameters and configuration for the backtest run
     * @return Results of the backtest analysis
     * @throws InvalidProtocolBufferException if there's an issue with protocol buffer processing
     */
    fun runBacktest(request: BacktestRequest): BacktestResult
}
