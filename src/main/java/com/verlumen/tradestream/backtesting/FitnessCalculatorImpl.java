package com.verlumen.tradestream.backtesting;

import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.verlumen.tradestream.strategies.Strategy;
import io.jenetics.Gene;
import io.jenetics.Genotype;
import java.util.function.Function;

/**
 * Implementation of the FitnessCalculator interface which calculates fitness scores for genetic
 * algorithm individuals using backtesting.
 */
final class FitnessCalculatorImpl implements FitnessCalculator {
  private final BacktestRequestFactory backtestRequestFactory;
  private final BacktestRunner backtestRunner;
  private final GenotypeConverter genotypeConverter;

  @Inject
  FitnessCalculatorImpl(
    BacktestRequestFactory backtestRequestFactory,
    BacktestRunner backtestRunner,
    GenotypeConverter genotypeConverter) {
    this.backtestRequestFactory = backtestRequestFactory;
    this.backtestRunner = backtestRunner;
    this.genotypeConverter = genotypeConverter;
  }

  @Override
  public Function<Genotype<?>, Double> createFitnessFunction(GAOptimizationRequest request) {
    return genotype -> {
      try {
        Any params = genotypeConverter.convertToParameters(genotype, request.getStrategyType());

        BacktestRequest backtestRequest =
            backtestRequestFactory.create(
              request.getCandlesList(),
              Strategy.newBuilder()
                .setType(request.getStrategyType())
                .setParameters(params)
                .build());

        BacktestResult result = backtestRunner.runBacktest(backtestRequest);
        return result.getStrategyScore();
      } catch (Exception e) {
        // Penalize any invalid genotype by assigning the lowest possible fitness
        return Double.NEGATIVE_INFINITY;
      }
    };
  }
}
