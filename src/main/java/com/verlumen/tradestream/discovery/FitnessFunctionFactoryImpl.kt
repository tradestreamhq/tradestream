package com.verlumen.tradestream.discovery

import com.google.inject.Inject
import com.google.protobuf.Any
import com.verlumen.tradestream.backtesting.BacktestRequest
import com.verlumen.tradestream.backtesting.BacktestRequestFactory
import com.verlumen.tradestream.backtesting.BacktestResult
import com.verlumen.tradestream.backtesting.BacktestRunner
import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategyType
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
                    // Convert string to StrategyType for genotypeConverter (until #1511 is done)
                    val strategyType = StrategyType.valueOf(strategyName)
                    val params: Any = genotypeConverter.convertToParameters(genotype, strategyType)
                    val backtestRequest: BacktestRequest = createBacktestRequest(strategyName, strategyType, candles, params)
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
            strategyType: StrategyType,
            candles: List<Candle>,
            params: Any,
        ): BacktestRequest =
            backtestRequestFactory.create(
                candles,
                Strategy
                    .newBuilder()
                    .setType(strategyType)  // Keep for backwards compatibility
                    .setStrategyName(strategyName)  // New string-based identifier
                    .setParameters(params)
                    .build(),
            )
    }
