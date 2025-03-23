package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;
import com.verlumen.tradestream.marketdata.Candle;
import org.apache.beam.sdk.coders.KvCoder;
import org.apache.beam.sdk.coders.SerializableCoder;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;

/**
 * A PTransform that splits the input KV<String, ImmutableList<Candle>> into one record
 * per strategy type.
 */
final class SplitByStrategyType 
    extends PTransform<PCollection<KV<String, ImmutableList<Candle>>>,
                       PCollection<KV<String, StrategyProcessingRequest>>> {

  private final SplitByStrategyTypeFn splitByStrategyTypeFn;

  @Inject
  SplitByStrategyType(SplitByStrategyTypeFn splitByStrategyTypeFn) {
      this.splitByStrategyTypeFn = splitByStrategyTypeFn;
  }

  @Override
  public PCollection<KV<String, StrategyProcessingRequest>> expand(
      PCollection<KV<String, ImmutableList<Candle>>> input) {
    return input
        .apply("SplitPerStrategyType", ParDo.of(splitByStrategyTypeFn))
        .setCoder(KvCoder.of(
            StringUtf8Coder.of(),
            SerializableCoder.of(StrategyProcessingRequest.class)
        ));
  }

  private static class SplitByStrategyTypeFn 
      extends DoFn<KV<String, ImmutableList<Candle>>, KV<String, StrategyProcessingRequest>> {
    @Inject
    SplitByStrategyTypeFn() {}

    @ProcessElement
    public void processElement(
            @Element KV<String, ImmutableList<Candle>> element,
            OutputReceiver<KV<String, StrategyProcessingRequest>> out) {
      String key = element.getKey();
      ImmutableList<Candle> candles = element.getValue();

      for (StrategyType strategyType : StrategyConstants.supportedStrategyTypes) {
        StrategyProcessingRequest request = new StrategyProcessingRequest(strategyType, candles);
        out.output(KV.of(key, request));
      }
    }
  }
}
