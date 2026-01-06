package com.verlumen.tradestream.discovery

import com.google.inject.Inject
import com.google.protobuf.Any
import com.verlumen.tradestream.backtesting.BacktestRequest
import com.verlumen.tradestream.backtesting.BacktestRequestFactory
import com.verlumen.tradestream.backtesting.BacktestResult
import com.verlumen.tradestream.backtesting.BacktestRunner
import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.strategies.Strategy
import java.util.function.Function

/**
 * Implementation of the FitnessFunctionFactory interface which calculates fitness scores for genetic
 * algorithm individuals using backtesting.
 */
class FitnessFunctionFactoryImpl
    @Inject
    constructor(
        private val backtestRequestFactory: BacktestRequestFactory,
        private val backtestRunner: BacktestRunner,
        private val genotypeConverter: GenotypeConverter,
    ) : FitnessFunctionFactory {
        override fun create(
            strategyName: String,
            candles: List<Candle>,
        ): FitnessFunction =
            Function { genotype ->
                try {
                    // Convert genotype to strategy parameters using string-based lookup
                    val params: Any = genotypeConverter.convertToParameters(genotype, strategyName)
                    val backtestRequest: BacktestRequest = createBacktestRequest(strategyName, candles, params)
                    val result: BacktestResult = backtestRunner.runBacktest(backtestRequest)
                    result.strategyScore
                } catch (e: Exception) {
                    // Penalize any invalid genotype by assigning the lowest possible fitness
                    // Consider logging the exception e here if appropriate
                    Double.NEGATIVE_INFINITY
                }
            }

        private fun createBacktestRequest(
            strategyName: String,
            candles: List<Candle>,
            params: Any,
        ): BacktestRequest =
            backtestRequestFactory.create(
                candles,
                Strategy
                    .newBuilder()
                    .setStrategyName(strategyName)
                    .setParameters(params)
                    .build(),
            )
    }
