package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.strategies.StrategyType
import java.io.Serializable

/** Defines the contract for calculating fitness scores using backtesting. */
interface FitnessFunctionFactory : Serializable {
    /**
     * Creates a fitness function for the genetic algorithm.
     *
     * @param strategyType the type of strategy to create a fitness function for
     * @param candles the list of candles (market data) to be used for fitness calculation
     * @return a function that evaluates the fitness of a genotype, returning a Double
     */
    fun create(
        strategyType: StrategyType,
        candles: List<Candle>,
    ): FitnessFunction
}
