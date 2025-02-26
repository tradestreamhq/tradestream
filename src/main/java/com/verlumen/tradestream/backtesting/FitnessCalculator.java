package com.verlumen.tradestream.backtesting;

import io.jenetics.DoubleGene;
import io.jenetics.Genotype;
import java.util.function.Function;

/**
 * Defines the contract for calculating fitness scores using backtesting.
 */
interface FitnessCalculator {
    /**
     * Creates a fitness function for the genetic algorithm.
     *
     * @param request the GA optimization request
     * @return a function that evaluates the fitness of a genotype
     */
    Function<Genotype<DoubleGene>, Double> createFitnessFunction(GAOptimizationRequest request);
}
