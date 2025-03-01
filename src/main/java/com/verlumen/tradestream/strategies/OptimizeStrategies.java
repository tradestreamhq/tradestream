package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.google.common.flogger.FluentLogger;
import com.google.inject.Inject;
import com.verlumen.tradestream.backtesting.BestStrategyResponse;
import com.verlumen.tradestream.backtesting.GAOptimizationRequest;
import com.verlumen.tradestream.backtesting.GeneticAlgorithmOrchestrator;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.ta4j.BarSeriesBuilder;
import org.apache.beam.sdk.state.StateSpec;
import org.apache.beam.sdk.state.StateSpecs;
import org.apache.beam.sdk.state.ValueState;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.DoFn.StateId;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.TypeDescriptor;
import org.ta4j.core.BarSeries;

/**
 * A PTransform that optimizes strategies for each incoming candle batch.
 * Uses the genetic algorithm orchestrator to find the best strategy parameters.
 */
public class OptimizeStrategies 
    extends PTransform<PCollection<KV<String, ImmutableList<Candle>>>, 
                      PCollection<KV<String, StrategyState>>> {

  private static final FluentLogger logger = FluentLogger.forEnclosingClass();
  
  private final GeneticAlgorithmOrchestrator geneticAlgorithmOrchestrator;
  
  @Inject
  OptimizeStrategies(
      GeneticAlgorithmOrchestrator geneticAlgorithmOrchestrator) {
    this.geneticAlgorithmOrchestrator = geneticAlgorithmOrchestrator;
  }
  
  @Override
  public PCollection<KV<String, StrategyState>> expand(
      PCollection<KV<String, ImmutableList<Candle>>> input) {
    
    return input.apply("OptimizeStrategiesForCandles", 
        ParDo.of(new OptimizeStrategiesDoFn(geneticAlgorithmOrchestrator)))
        .setTypeDescriptor(new TypeDescriptor<KV<String, StrategyState>>() {});
  }
  
  /**
   * Stateful DoFn that maintains strategy state and performs optimization.
   */
  private static class OptimizeStrategiesDoFn 
      extends DoFn<KV<String, ImmutableList<Candle>>, KV<String, StrategyState>> {
    
    @StateId("strategyState")
    private final StateSpec<ValueState<StrategyState>> strategyStateSpec = StateSpecs.value();
    
    private final GeneticAlgorithmOrchestrator geneticAlgorithmOrchestrator;
    
    OptimizeStrategiesDoFn(
        GeneticAlgorithmOrchestrator geneticAlgorithmOrchestrator) {
      this.geneticAlgorithmOrchestrator = geneticAlgorithmOrchestrator;
    }
    
    @ProcessElement
    public void processElement(
        ProcessContext context,
        @StateId("strategyState") ValueState<StrategyState> strategyStateValue) {
      
      KV<String, ImmutableList<Candle>> element = context.element();
      String key = element.getKey();
      ImmutableList<Candle> candles = element.getValue();
      
      // Skip empty candle lists
      if (candles == null || candles.isEmpty()) {
        logger.atWarning().log("Received empty candle list for key: %s", key);
        return;
      }
      
      // Convert candles to a BarSeries
      BarSeries barSeries = BarSeriesBuilder.createBarSeries(candles);
      
      // Get or initialize strategy state
      StrategyState state = strategyStateValue.read();
      if (state == null) {
        logger.atInfo().log("Initializing strategy state for key: %s", key);
        state = StrategyState.initialize(barSeries);
      }
      
      // Optimize each strategy type
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
          logger.atWarning().withCause(e).log(
              "Error optimizing strategy %s for key: %s", strategyType, key);
        }
      }
      
      // Select the best strategy based on optimization scores
      state = state.selectBestStrategy(barSeries);
      
      // Update state and output the optimized strategy state
      strategyStateValue.write(state);
      context.output(KV.of(key, state));
    }
  }
}
