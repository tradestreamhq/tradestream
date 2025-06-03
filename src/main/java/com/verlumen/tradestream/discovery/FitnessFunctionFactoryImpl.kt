package com.verlumen.tradestream.discovery

import com.google.inject.Inject
import com.google.protobuf.Any // Assuming this is com.google.protobuf.Any
import com.verlumen.tradestream.backtesting.BacktestRequest
import com.verlumen.tradestream.backtesting.BacktestRequestFactory
import com.verlumen.tradestream.backtesting.BacktestResult
import com.verlumen.tradestream.backtesting.BacktestRunner
import com.verlumen.tradestream.backtesting.GAOptimizationRequest
import com.verlumen.tradestream.strategies.Strategy
import io.jenetics.Genotype

/**
 * Implementation of the FitnessFunctionFactory interface which calculates fitness scores for genetic
 * algorithm individuals using backtesting.
 */
internal class FitnessFunctionFactoryImpl
    @Inject
    constructor(
        private val backtestRequestFactory: BacktestRequestFactory,
        private val backtestRunner: BacktestRunner,
        private val genotypeConverter: GenotypeConverter, // Assuming GenotypeConverter is a defined class/interface
    ) : FitnessFunctionFactory {
        override fun create(request: GAOptimizationRequest): (Genotype<*>) -> Double =
            { genotype ->
                try {
                    val params: Any = genotypeConverter.convertToParameters(genotype, request.strategyType)

                    val backtestRequest: BacktestRequest =
                        backtestRequestFactory.create(
                            request.candlesList, // Assumes Kotlin synthetic property access
                            Strategy
                                .newBuilder()
                                .setType(request.strategyType) // Assumes Kotlin synthetic property access
                                .setParameters(params)
                                .build(),
                        )

                    val result: BacktestResult = backtestRunner.runBacktest(backtestRequest)
                    result.strategyScore // Assumes Kotlin synthetic property access
                } catch (e: Exception) {
                    // Penalize any invalid genotype by assigning the lowest possible fitness
                    // Consider logging the exception e here if appropriate
                    Double.NEGATIVE_INFINITY
                }
            }
    }
