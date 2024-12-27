package com.verlumen.tradestream.ga;

import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.backtesting.BacktestRequest;
import com.verlumen.tradestream.backtesting.BacktestResult;
import com.verlumen.tradestream.backtesting.BacktestRunner;
import com.verlumen.tradestream.ga.GAOptimizationRequest;
import com.verlumen.tradestream.ga.BestStrategyResponse;
import com.verlumen.tradestream.ga.GAServiceGrpc.GAServiceImplBase;
import com.verlumen.tradestream.strategies.StrategyManager;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.Strategies.StrategyParameters;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import io.jenetics.*;
import io.jenetics.engine.Engine;
import io.jenetics.engine.EvolutionStatistics;
import io.jenetics.engine.EvolutionResult;
import io.jenetics.util.IntRange;

import java.util.function.Function;
import java.util.logging.Logger;

/**
 * GA Service Implementation that runs a genetic algorithm to find optimal parameters 
 * for a given strategy type, using the BacktestRunner as the fitness function.
 */
public final class GAServiceImpl extends GAServiceImplBase {
  private static final Logger logger = Logger.getLogger(GAServiceImpl.class.getName());

  private final BacktestRunner backtestRunner;
  private final StrategyManager strategyManager;

  @Inject
  public GAServiceImpl(BacktestRunner backtestRunner, StrategyManager strategyManager) {
    this.backtestRunner = backtestRunner;
    this.strategyManager = strategyManager;
  }

  @Override
  public void requestOptimization(
      GAOptimizationRequest request, 
      StreamObserver<BestStrategyResponse> responseObserver) {

    try {
      // Extract the inner backtest request
      BacktestRequest btRequest = request.getBacktestRequest();

      // Determine which strategy type we are optimizing
      StrategyType strategyType = btRequest.getStrategyType();
      logger.info(() -> "Starting GA optimization for " + strategyType);

      // Create the Jenetics engine specialized to this StrategyType
      Engine<IntegerGene, Double> engine = createEngine(btRequest);

      // Evolve
      EvolutionStatistics<Double, ?> statistics = EvolutionStatistics.ofNumber();
      Phenotype<IntegerGene, Double> best = engine.stream()
          .limit(50)          // e.g. 50 generations
          .peek(statistics)
          .collect(EvolutionResult.toBestPhenotype());

      double bestFitness = best.fitness();
      // Convert best genotype -> StrategyParameters
      StrategyParameters bestParams = decodeStrategyParameters(best, strategyType);

      BestStrategyResponse response = BestStrategyResponse.newBuilder()
          .setParameters(bestParams)
          .setFitness(bestFitness)
          .build();

      logger.info("Best GA solution = " + bestParams + "; fitness = " + bestFitness);
      responseObserver.onNext(response);
      responseObserver.onCompleted();

    } catch (Exception e) {
      logger.severe("Error during GA optimization: " + e.getMessage());
      responseObserver.onError(
          Status.INTERNAL
              .withDescription(e.getMessage())
              .withCause(e)
              .asRuntimeException());
    }
  }

  /**
   * Creates a Jenetics Engine for a given BacktestRequest. The genotype encoding is just an example.
   */
  private Engine<IntegerGene, Double> createEngine(BacktestRequest btRequest) {
    // For demonstration, we'll assume we want to optimize 2 integer parameters in [1..50].
    // In reality, you'd build this genotype based on the StrategyType, e.g. if it's SmaRsi, 
    // you might encode [rsiPeriod, movingAveragePeriod, oversoldThreshold, overboughtThreshold].
    int parameterCount = 2;

    Function<Genotype<IntegerGene>, Double> fitnessFunction = gt -> evaluateFitness(gt, btRequest);

    return Engine
      .builder(fitnessFunction, Genotype.of(IntegerChromosome.of(IntRange.of(1, 50), parameterCount)))
      .populationSize(30)
      .maximizing()      // We assume a higher backtest score is better
      .build();
  }

  /**
   * Uses the BacktestRunner to compute a fitness metric from the genotype's parameters.
   */
  private double evaluateFitness(Genotype<IntegerGene> gt, BacktestRequest btRequest) {
    // Convert genotype => StrategyParameters => run backtest => return overall_score 
    StrategyParameters sp;
    try {
      sp = decodeStrategyParameters(gt, btRequest.getStrategyType());
    } catch (InvalidProtocolBufferException e) {
      return 0.0; 
    }

    // Rebuild a BacktestRequest with these new parameters
    BacktestRequest tunedRequest = btRequest.toBuilder()
      .clearStrategyParameters()                // we will re-pack with our updated parameters
      .setStrategyParameters(Any.pack(sp))      // store the newly generated parameters
      .build();

    // Run the backtest
    BacktestResult result = backtestRunner.runBacktest(tunedRequest);
    // Use the result’s overall_score as our fitness
    return result.getOverallScore();
  }

  /**
   * Decodes the genotype into the appropriate StrategyParameters message for the given StrategyType.
   */
  private StrategyParameters decodeStrategyParameters(Genotype<IntegerGene> gt, StrategyType type)
      throws InvalidProtocolBufferException {
    // For demonstration, we only handle 2-int parameters. 
    // A real system might handle more or switch on type to build different param messages.
    int paramA = gt.getChromosome().getGene(0).intValue();
    int paramB = gt.getChromosome().getGene(1).intValue();

    // Example: If it’s SmaRsi, use SmaRsiParameters:
    // SmaRsiParameters p = SmaRsiParameters.newBuilder()
    //     .setRsiPeriod(paramA)
    //     .setMovingAveragePeriod(paramB)
    //     .setOversoldThreshold(30)
    //     .setOverboughtThreshold(70)
    //     .build();
    //
    // return Strategies.StrategyParameters.newBuilder()
    //     .setSmaRsiParameters(p)
    //     .build();

    // For now, just build a dummy StrategyParameters for demonstration:
    return StrategyParameters.newBuilder()
        .setSmaRsiParameters(
            com.verlumen.tradestream.strategies.SmaRsiParameters.newBuilder()
                .setRsiPeriod(paramA)
                .setMovingAveragePeriod(paramB)
                .setOversoldThreshold(30)
                .setOverboughtThreshold(70)
                .build())
        .build();
  }
}
