package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.google.common.flogger.FluentLogger;
import com.google.inject.Inject;
import com.verlumen.tradestream.backtesting.BestStrategyResponse;
import com.verlumen.tradestream.backtesting.GAOptimizationRequest;
import com.verlumen.tradestream.backtesting.GeneticAlgorithmOrchestrator;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.ta4j.BarSeriesFactory;
import org.apache.beam.sdk.state.StateSpec;
import org.apache.beam.sdk.state.StateSpecs;
import org.apache.beam.sdk.state.ValueState;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.DoFn.StateId;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.ta4j.core.BarSeries;

/**
 * A PTransform that optimizes strategies for each incoming candle batch.
 * Uses the genetic algorithm orchestrator to find the best strategy parameters.
 */
public class OptimizeStrategies 
    extends PTransform<PCollection<KV<String, ImmutableList<Candle>>>, 
                      PCollection<KV<String, StrategyState>>> {

  private static final FluentLogger logger = FluentLogger.forEnclosingClass();
  private final OptimizeStrategiesDoFn optimizeStrategiesDoFn;

  @Inject
  public OptimizeStrategies(OptimizeStrategiesDoFn optimizeStrategiesDoFn) {
    this.optimizeStrategiesDoFn = optimizeStrategiesDoFn;
  }

  @Override
  public PCollection<KV<String, StrategyState>> expand(
      PCollection<KV<String, ImmutableList<Candle>>> input) {

    return input.apply("OptimizeStrategiesForCandles", ParDo.of(optimizeStrategiesDoFn));
  }

  /**
   * Stateful DoFn that maintains strategy state and performs optimization.
   */
  static class OptimizeStrategiesDoFn 
      extends DoFn<KV<String, ImmutableList<Candle>>, KV<String, StrategyState>> {

    @StateId("strategyState")
    private final StateSpec<ValueState<StrategyState>> strategyStateSpec = StateSpecs.value();

    private final BarSeriesFactory barSeriesFactory;
    private final GeneticAlgorithmOrchestrator geneticAlgorithmOrchestrator; 
    private final StrategyState.Factory stateFactory;

    @Inject
    public OptimizeStrategiesDoFn(
        BarSeriesFactory barSeriesFactory,
        GeneticAlgorithmOrchestrator geneticAlgorithmOrchestrator,
        StrategyState.Factory stateFactory) {
      this.barSeriesFactory = barSeriesFactory;
      this.geneticAlgorithmOrchestrator = geneticAlgorithmOrchestrator;
      this.stateFactory = stateFactory;
    }

    @ProcessElement
    public void processElement(ProcessContext context,
                               @StateId("strategyState") ValueState<StrategyState> strategyStateValue) {

      KV<String, ImmutableList<Candle>> element = context.element();
      String key = element.getKey();
      ImmutableList<Candle> candles = element.getValue();

      if (candles == null || candles.isEmpty()) {
        logger.atWarning().log("Received empty candle list for key: %s", key);
        return;
      }

      BarSeries barSeries = barSeriesFactory.createBarSeries(candles);
      StrategyState state = strategyStateValue.read();
      if (state == null) {
        logger.atInfo().log("Initializing strategy state for key: %s", key);
        state = stateFactory.create();
      }

      // Loop over each strategy type to optimize.
      for (StrategyType strategyType : state.getStrategyTypes()) {
        try {
          GAOptimizationRequest request = GAOptimizationRequest.newBuilder()
              .setStrategyType(strategyType)
              .addAllCandles(candles)
              .build();

          logger.atInfo().log("Optimizing strategy %s for key: %s", strategyType, key);
          BestStrategyResponse response = geneticAlgorithmOrchestrator.runOptimization(request);
          state.updateRecord(strategyType, response.getBestStrategyParameters(), response.getBestScore());

        } catch (Exception e) {
          logger.atWarning().withCause(e).log("Error optimizing strategy %s for key: %s", strategyType, key);
        }
      }

      state = state.selectBestStrategy(barSeries);
      strategyStateValue.write(state);
      context.output(KV.of(key, state));
    }
  }
}
