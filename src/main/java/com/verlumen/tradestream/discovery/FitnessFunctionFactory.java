package com.verlumen.tradestream.discovery;

import java.io.Serializable;

/** Defines the contract for calculating fitness scores using backtesting. */
public interface FitnessFunctionFactory extends Serializable {
  /**
   * Creates a fitness function for the genetic algorithm.
   *
   * @param params the fitness calculation parameters
   * @return a function that evaluates the fitness of a genotype
   */
  FitnessFunction create(FitnessFunctionParams params);
}
