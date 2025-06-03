package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.backtesting.GAOptimizationRequest
import io.jenetics.Genotype
import java.io.Serializable
import java.util.function.Function

/** Defines the contract for creating fitness functions for genetic algorithms. */
interface FitnessFunctionFactory : Serializable {
    /**
     * Creates a fitness function for the genetic algorithm.
     *
     * @param request the GA optimization request, containing parameters for fitness calculation
     * @return a function that evaluates the fitness of a genotype, returning a Double
     */
    fun create(request: GAOptimizationRequest): Function<Genotype<*>, Double>
}
