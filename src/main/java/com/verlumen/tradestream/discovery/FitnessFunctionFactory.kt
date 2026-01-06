package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.marketdata.Candle
import java.io.Serializable

/** Defines the contract for calculating fitness scores using backtesting. */
interface FitnessFunctionFactory : Serializable {
    /**
     * Creates a fitness function for the genetic algorithm.
     *
     * @param strategyName the string name of the strategy (e.g., "MACD_CROSSOVER")
     * @param candles the list of candles (market data) to be used for fitness calculation
     * @return a function that evaluates the fitness of a genotype, returning a Double
     */
    fun create(
        strategyName: String,
        candles: List<Candle>,
    ): FitnessFunction
}
