package com.verlumen.tradestream.backtesting;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.GenotypeConverter;
import io.jenetics.Phenotype;
import io.jenetics.engine.Engine;
import io.jenetics.engine.EvolutionResult;

/**
 * Implementation of the GeneticAlgorithmOrchestrator interface. This class coordinates the overall
 * GA optimization process but delegates specific responsibilities to specialized classes.
 */
final class GeneticAlgorithmOrchestratorImpl implements GeneticAlgorithmOrchestrator {
  private final GAEngineFactory engineFactory;
  private final GenotypeConverter genotypeConverter;

  @Inject
  GeneticAlgorithmOrchestratorImpl(
      GAEngineFactory engineFactory, GenotypeConverter genotypeConverter) {
    this.engineFactory = engineFactory;
    this.genotypeConverter = genotypeConverter;
  }

  /**
   * Runs the genetic algorithm optimization for a given trading strategy.
   *
   * @param request the GA optimization request containing the strategy type, candles, and other
   *     settings
   * @return a response containing the best strategy parameters and corresponding fitness score
   * @throws IllegalArgumentException if the request's candles list is empty
   */
  @Override
  public BestStrategyResponse runOptimization(GAOptimizationRequest request) {
    checkArgument(!request.getCandlesList().isEmpty(), "Candles list cannot be empty");

    // Configure the genetic algorithm engine with the strategy and backtest service
    Engine<?, Double> engine = engineFactory.createEngine(request);

    // Execute the GA and collect the best phenotype from the evolution process
    Phenotype<?, Double> best =
        engine.stream()
            .limit(getMaxGenerations(request))
            .collect(EvolutionResult.toBestPhenotype());

    // Convert the best genotype into strategy parameters
    Any bestParams =
        genotypeConverter.convertToParameters(best.genotype(), request.getStrategyType());

    return BestStrategyResponse.newBuilder()
        .setBestStrategyParameters(bestParams)
        .setBestScore(best.fitness())
        .build();
  }

  private int getMaxGenerations(GAOptimizationRequest request) {
    return request.getMaxGenerations() > 0
        ? request.getMaxGenerations()
        : GAConstants.DEFAULT_MAX_GENERATIONS;
  }
}
