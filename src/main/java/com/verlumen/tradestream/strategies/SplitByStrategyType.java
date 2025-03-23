package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.marketdata.Candle;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;

/**
 * A PTransform that splits the input KV<String, ImmutableList<Candle>> into one record
 * per strategy type.
 */
class SplitByStrategyType 
    extends PTransform<PCollection<KV<String, ImmutableList<Candle>>>,
                       PCollection<KV<String, StrategyProcessingRequest>>> {

  @Override
  public PCollection<KV<String, StrategyProcessingRequest>> expand(
      PCollection<KV<String, ImmutableList<Candle>>> input) {
    return input.apply("SplitPerStrategyType", ParDo.of(new SplitByStrategyTypeFn()));
  }
  
  private static class SplitByStrategyTypeFn 
      extends DoFn<KV<String, ImmutableList<Candle>>, KV<String, StrategyProcessingRequest>> {

    @ProcessElement
    public void processElement(
            @Element KV<String, ImmutableList<Candle>> element,
            OutputReceiver<KV<String, StrategyProcessingRequest>> out) {
      String key = element.getKey();
      ImmutableList<Candle> candles = element.getValue();

      for (StrategyType strategyType : StrategyType.values()) {
        StrategyProcessingRequest request = new StrategyProcessingRequest(strategyType, candles);
        out.output(KV.of(key, request));
      }
    }
  }
}
