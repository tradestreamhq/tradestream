package com.verlumen.tradestream.backtesting;

import com.verlumen.tradestream.backtesting.GAOptimizationRequest;
import com.verlumen.tradestream.backtesting.BestStrategyResponse;

/**
 * Orchestrates a genetic/evolutionary search for the best strategy parameters.
 * <p>
 * Typically, implementations of this interface:
 * <ul>
 *   <li>Generate candidate parameter sets (possibly with a library like Jenetics).</li>
 *   <li>Call {@link BacktestService} repeatedly to evaluate each candidate.</li>
 *   <li>Track the best overall result and parameter set.</li>
 *   <li>Return a {@link BestStrategyResponse} containing the top parameters and score.</li>
 * </ul>
 */
public interface GeneticAlgorithmOrchestrator {

    /**
     * Runs a genetic algorithm-based optimization to discover the best
     * strategy parameters for a given dataset and strategy type.
     *
     * @param request The GA optimization request, including candle data,
     *                strategy type, and any optional GA config.
     * @return A response containing the best discovered parameter set (in
     *         {@code google.protobuf.Any} form) and the best score.
     */
    BestStrategyResponse runOptimization(GAOptimizationRequest request);
}
