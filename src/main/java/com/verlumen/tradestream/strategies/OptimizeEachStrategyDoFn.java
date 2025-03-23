package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
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
import org.apache.beam.sdk.values.KV;
import org.ta4j.core.BarSeries;

/**
 * DoFn that processes each strategy type in isolation while maintaining shared state.
 */
public class OptimizeEachStrategyDoFn 
    extends DoFn<KV<String, StrategyProcessingRequest>, KV<String, StrategyState>> {

  private final BarSeriesFactory barSeriesFactory;
  private final GeneticAlgorithmOrchestrator geneticAlgorithmOrchestrator;
  private final StrategyState.Factory stateFactory;

  @StateId("strategyState")
  private final StateSpec<ValueState<StrategyState>> stateSpec = StateSpecs.value();

  @Inject
  public OptimizeEachStrategyDoFn(BarSeriesFactory barSeriesFactory,
                                  GeneticAlgorithmOrchestrator geneticAlgorithmOrchestrator,
                                  StrategyState.Factory stateFactory) {
    this.barSeriesFactory = barSeriesFactory;
    this.geneticAlgorithmOrchestrator = geneticAlgorithmOrchestrator;
    this.stateFactory = stateFactory;
  }

  @ProcessElement
  public void processElement(ProcessContext context,
                             @StateId("strategyState") ValueState<StrategyState> sharedState) {
    KV<String, StrategyProcessingRequest> element = context.element();
    String key = element.getKey();
    StrategyProcessingRequest request = element.getValue();
    StrategyType strategyType = request.getStrategyType();
    ImmutableList<Candle> candles = request.getCandles();

    if (candles == null || candles.isEmpty()) {
      // Optionally log a warning here.
      return;
    }

    // Read or initialize the shared state.
    StrategyState state = sharedState.read();
    if (state == null) {
      state = stateFactory.create();
    }

    BarSeries barSeries = barSeriesFactory.createBarSeries(candles);

    GAOptimizationRequest optimizationRequest = GAOptimizationRequest.newBuilder()
        .setStrategyType(strategyType)
        .addAllCandles(candles)
        .build();

    try {
      BestStrategyResponse response = geneticAlgorithmOrchestrator.runOptimization(optimizationRequest);
      state.updateRecord(strategyType, response.getBestStrategyParameters(), response.getBestScore());
    } catch (Exception e) {
      // Handle or log the exception for this strategy type.
    }

    StrategyState updatedState = state.selectBestStrategy(barSeries);
    sharedState.write(updatedState);
    context.output(KV.of(key, updatedState));
  }
}
