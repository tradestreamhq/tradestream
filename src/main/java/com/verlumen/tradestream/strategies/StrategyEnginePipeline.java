package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.google.common.flogger.FluentLogger;
import com.google.inject.Inject;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.signals.GenerateTradeSignals;
import com.verlumen.tradestream.signals.PublishTradeSignals;
import com.verlumen.tradestream.signals.TradeSignal;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.Filter;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PDone;

/**
 * Component class that ties all of the strategy engine transforms together.
 * This can be injected into the main App and applied to the candle stream.
 */
public class StrategyEnginePipeline {

  private static final FluentLogger logger = FluentLogger.forEnclosingClass();
  
  private final OptimizeStrategies optimizeStrategies;
  private final GenerateTradeSignals generateTradeSignals;
  private final PublishTradeSignals publishTradeSignals;
  
  @Inject
  StrategyEnginePipeline(
      OptimizeStrategies optimizeStrategies,
      GenerateTradeSignals generateTradeSignals,
      PublishTradeSignals publishTradeSignals,
      StoreCandlesDoFn storeCandlesDoFn) {
    this.optimizeStrategies = optimizeStrategies;
    this.generateTradeSignals = generateTradeSignals;
    this.publishTradeSignals = publishTradeSignals;
    this.storeCandlesDoFn = storeCandlesDoFn;
  }
  
  /**
   * Applies the strategy engine pipeline to a candle stream, generating and publishing trade signals.
   * 
   * @param candles A keyed collection of candle batches
   * @return PDone indicating the pipeline has been applied
   */
  public PDone apply(PCollection<KV<String, ImmutableList<Candle>>> candles) {
    logger.atInfo().log("Applying strategy engine pipeline to candle stream");
    
    // Filter out empty candle lists (defensive)
    PCollection<KV<String, ImmutableList<Candle>>> filteredCandles = 
        candles.apply("FilterEmptyCandleLists", 
            Filter.by(kv -> kv.getValue() != null && !kv.getValue().isEmpty()));
    
    // Store candles in state for signal generation (side effect)
    filteredCandles.apply("StoreCandles", ParDo.of(storeCandlesDoFn));
    
    // Optimize strategies and generate signals
    PCollection<KV<String, StrategyState>> optimizedStrategies = 
        filteredCandles.apply("OptimizeStrategies", optimizeStrategies);
    
    PCollection<KV<String, TradeSignal>> signals = 
        optimizedStrategies.apply("GenerateTradeSignals", generateTradeSignals);
    
    // Publish actionable signals
    return signals.apply("PublishTradeSignals", publishTradeSignals);
  }
  
  /**
   * Helper DoFn that stores candles in state for later use in signal generation.
   * This creates a side-effect to ensure candles are available for the signal generation step.
   */
  private static class StoreCandlesDoFn extends DoFn<KV<String, ImmutableList<Candle>>, Void> {
    
    @StateId("storedCandles")
    private final StateSpec<ValueState<ImmutableList<Candle>>> storedCandlesSpec;

    @Inject
    StoreCandlesDoFn() {
      this.storedCandlesSpec = StateSpecs.value();
    }

    @ProcessElement
    public void processElement(
        ProcessContext context,
        @StateId("storedCandles") ValueState<ImmutableList<Candle>> storedCandlesState) {
      KV<String, ImmutableList<Candle>> element = context.element();
      storedCandlesState.write(element.getValue());
    }
  }
}
