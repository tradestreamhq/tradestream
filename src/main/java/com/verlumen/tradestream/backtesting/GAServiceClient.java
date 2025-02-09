package com.verlumen.tradestream.backtesting;

/**
 * Client for interacting with the Genetic Algorithm (GA) Service.
 * This service provides methods for triggering parameter optimization
 * runs for specified trading strategies.
 */
public interface GAServiceClient {

  /**
   * Requests the GA Service to perform a parameter optimization run.
   *
   * @param request The optimization request containing details like the
   *                strategy type, candle data, and optional GA configuration.
   * @return A {@link BestStrategyResponse} containing the best found
   *         strategy parameters and associated score.
   */
  BestStrategyResponse requestOptimization(GAOptimizationRequest request);
}
