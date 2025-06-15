package com.verlumen.tradestream.backtesting

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.strategies.Strategy
import java.io.Serializable

/**
 * Implementation of [BacktestRequestFactory] that builds [BacktestRequest] objects.
 *
 * This implementation uses standard constructor injection for dependencies.
 */
class BacktestRequestFactoryImpl
    @Inject
    constructor() : BacktestRequestFactory,
    Serializable {

    companion object {
        private const val serialVersionUID: Long = 1L
    }

    /**
     * Logger is marked as `transient` so that the non-serializable
     * `FluentLogger` does not get written to the serialization stream.
     */
    @Transient
    private val logger: FluentLogger = FluentLogger.forEnclosingClass()

    /**
     * Creates a [BacktestRequest] using the provided candles and strategy.
     * Logs the creation event.
     *
     * @param candles  The list of historical price candles.
     * @param strategy The trading strategy to be backtested.
     * @return A configured [BacktestRequest] object.
     */
    override fun create(
        candles: List<Candle>,
        strategy: Strategy,
    ): BacktestRequest {
        logger.atFine().log(
            "Creating BacktestRequest for strategy: %s with %d candles.",
            strategy.javaClass.simpleName,
            candles.size,
        )

        // Build the BacktestRequest using the protobuf builder
        val request =
            BacktestRequest
                .newBuilder()
                .addAllCandles(candles) // Add all candles
                .setStrategy(strategy)  // Attach the strategy
                .build()

        logger.atFine().log("BacktestRequest created successfully.")
        return request
    }
