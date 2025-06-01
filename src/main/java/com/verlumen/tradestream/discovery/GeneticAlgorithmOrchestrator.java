package com.verlumen.tradestream.discovery;

import java.io.Serializable;

/**
 * Orchestrates a genetic/evolutionary search for the best strategy parameters.
 *
 * <p>Typically, implementations of this interface:
 *
 * <ul>
 *   <li>Generate candidate parameter sets (possibly with a library like Jenetics).
 *   <li>Call {@link BacktestService} repeatedly to evaluate each candidate.
 *   <li>Track the best overall result and parameter set.
 *   <li>Return a {@link BestStrategyResponse} containing the top parameters and score.
 * </ul>
 */
public interface GeneticAlgorithmOrchestrator extends Serializable {

  /**
   * Runs a genetic algorithm-based optimization to discover the best strategy parameters for a
   * given dataset and strategy type.
   *
   * @param request The GA optimization request, including candle data, strategy type, and any
   *     optional GA config.
   * @return A response containing the best discovered parameter set (in {@code google.protobuf.Any}
   *     form) and the best score.
   */
  BestStrategyResponse runOptimization(GAOptimizationRequest request);
}
