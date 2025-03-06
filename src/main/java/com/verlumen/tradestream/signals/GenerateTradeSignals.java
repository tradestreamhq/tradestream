package com.verlumen.tradestream.pipeline.strategies;

import com.google.common.collect.ImmutableList;
import com.google.common.flogger.FluentLogger;
import com.google.inject.Inject;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.signals.TradeSignal;
import com.verlumen.tradestream.strategies.StrategyState;
import com.verlumen.tradestream.ta4j.BarSeriesBuilder;
import org.apache.beam.sdk.state.StateId;
import org.apache.beam.sdk.state.StateSpecs;
import org.apache.beam.sdk.state.ValueState;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.ta4j.core.BarSeries;

/**
 * Generates trade signals from optimized strategy states and candle data.
 */
final class GenerateTradeSignals extends 
    PTransform<PCollection<KV<String, StrategyState>>, PCollection<KV<String, TradeSignal>>> {

  private static final FluentLogger logger = FluentLogger.forEnclosingClass();
  
  private final GenerateSignalsDoFn generateSignalsDoFn;
  
  @Inject
  GenerateTradeSignals(GenerateSignalsDoFn generateSignalsDoFn) {
      this.generateSignalsDoFn = generateSignalsDoFn;
  }
  
  @Override
  public PCollection<KV<String, TradeSignal>> expand(
      PCollection<KV<String, StrategyState>> input) {
    
    return input.apply("GenerateSignalsFromOptimizedStrategies", ParDo.of(generateSignalsDoFn));
  }
  
  /**
   * Stateful DoFn that maintains the last signal and generates new signals based on
   * the optimized strategy.
   */
  private static class GenerateSignalsDoFn 
      extends DoFn<KV<String, StrategyState>, KV<String, TradeSignal>> {
    
    @StateId("lastCandles")
    private final StateSpec<ValueState<ImmutableList<Candle>>> lastCandlesSpec = StateSpecs.value();
    
    @StateId("lastSignal")
    private final StateSpec<ValueState<TradeSignal>> lastSignalSpec = StateSpecs.value();
    
    @Inject
    GenerateSignalsDoFn() {}
    
    @ProcessElement
    public void processElement(
        ProcessContext context,
        @StateId("lastCandles") ValueState<ImmutableList<Candle>> lastCandlesState,
        @StateId("lastSignal") ValueState<TradeSignal> lastSignalState) {
      
      KV<String, StrategyState> element = context.element();
      String key = element.getKey();
      StrategyState strategyState = element.getValue();
      
      // Get the last signal (or initialize if none)
      TradeSignal lastSignal = lastSignalState.read();
      if (lastSignal == null) {
        lastSignal = TradeSignal.newBuilder()
            .setType(TradeSignal.TradeSignalType.NONE)
            .build();
      }
      
      // Retrieve the last candles - we need these to generate the signal
      ImmutableList<Candle> candles = lastCandlesState.read();
      if (candles == null || candles.isEmpty()) {
        logger.atWarning().log("No candle data available for key: %s. Cannot generate signal.", key);
        return;
      }
      
      // Get the most recent candle for price and timestamp information
      Candle lastCandle = candles.get(candles.size() - 1);
      
      // Convert candles to BarSeries for TA4J
      BarSeries barSeries = BarSeriesBuilder.createBarSeries(candles);
      
      // Generate the trade signal
      TradeSignal signal = generateSignal(key, strategyState, barSeries, lastCandle);
      
      // Update state and output the signal
      lastSignalState.write(signal);
      context.output(KV.of(key, signal));
    }
    
    private TradeSignal generateSignal(
        String key, StrategyState state, BarSeries barSeries, Candle candle) {
      
      TradeSignal.Builder signalBuilder = TradeSignal.newBuilder();
      int endIndex = barSeries.getEndIndex();
      
      try {
        // Get the current TA4J strategy
        org.ta4j.core.Strategy currentStrategy = state.getCurrentStrategy(barSeries);
        
        // Check entry/exit conditions
        if (currentStrategy.shouldEnter(endIndex)) {
          signalBuilder.setType(TradeSignal.TradeSignalType.BUY)
              .setTimestamp(candle.getTimestamp().getSeconds() * 1000)
              .setPrice(candle.getClose());
          logger.atInfo().log("Generated BUY signal for %s at price %f", key, candle.getClose());
        } else if (currentStrategy.shouldExit(endIndex)) {
          signalBuilder.setType(TradeSignal.TradeSignalType.SELL)
              .setTimestamp(candle.getTimestamp().getSeconds() * 1000)
              .setPrice(candle.getClose());
          logger.atInfo().log("Generated SELL signal for %s at price %f", key, candle.getClose());
        } else {
          signalBuilder.setType(TradeSignal.TradeSignalType.NONE);
        }
        
        // Attach strategy information
        signalBuilder.setStrategy(state.toStrategyMessage());
        
      } catch (Exception e) {
        logger.atSevere().withCause(e).log("Error generating signal for %s", key);
        signalBuilder.setType(TradeSignal.TradeSignalType.ERROR)
            .setReason("Error generating trade signal: " + e.getMessage());
      }
      
      return signalBuilder.build();
    }
  }
}
