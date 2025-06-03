package com.verlumen.tradestream.discovery;

import io.jenetics.Genotype;
import java.io.Serializable;
import java.util.function.Function;

/** Defines the contract for calculating fitness scores using backtesting. */
public interface FitnessCalculator extends Serializable {
  /**
   * Creates a fitness function for the genetic algorithm.
   *
   * @param params the fitness calculation parameters
   * @return a function that evaluates the fitness of a genotype
   */
  Function<Genotype<?>, Double> createFitnessFunction(FitnessCalculationParams params);
}
