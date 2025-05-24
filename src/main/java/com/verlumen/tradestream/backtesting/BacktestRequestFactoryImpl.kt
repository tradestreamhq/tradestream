package com.verlumen.tradestream.backtesting

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.verlumen.tradestream.marketdata.Candle

/**
 * Implementation of [BacktestRequestFactory] that builds [BacktestRequest] objects.
 *
 * This implementation uses standard constructor injection for dependencies.
 */
class BacktestRequestFactoryImpl @Inject constructor() : BacktestRequestFactory {

    // Initialize FluentLogger for logging within this class
    private val logger = FluentLogger.forEnclosingClass()

    /**
     * Creates a [BacktestRequest] using the provided candles and strategy.
     * Logs the creation event.
     *
     * @param candles The list of historical price candles.
     * @param strategy The trading strategy to be backtested.
     * @return A configured [BacktestRequest] object.
     */
    override fun create(candles: List<Candle>, strategy: Strategy): BacktestRequest {
        logger.atFine().log("Creating BacktestRequest for strategy: %s with %d candles.", strategy.javaClass.simpleName, candles.size)

        // Build the BacktestRequest using the protobuf builder
        val request = BacktestRequest.newBuilder()
            .addAllCandles(candles) // AddAll handles the List<Candle>
            .setStrategy(strategy)  // Set the strategy
            .build()

        logger.atFine().log("BacktestRequest created successfully.")
        return request
    }
}
