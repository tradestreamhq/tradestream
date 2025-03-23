package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;
import com.verlumen.tradestream.marketdata.Candle;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;

/**
 * A composite PTransform that first splits the input per strategy type and then processes
 * each strategy type in isolation while sharing the state.
 */
final class OptimizeStrategiesIsolated 
    extends PTransform<PCollection<KV<String, ImmutableList<Candle>>>, PCollection<KV<String, StrategyState>>> {

  private final OptimizeEachStrategyDoFn optimizeEachStrategyDoFn;
  private final SplitByStrategyType splitByStrategyType;

  @Inject
  OptimizeStrategiesIsolated(OptimizeEachStrategyDoFn optimizeEachStrategyDoFn,
                             SplitByStrategyType splitByStrategyType) {
    this.optimizeEachStrategyDoFn = optimizeEachStrategyDoFn;
    this.splitByStrategyType = splitByStrategyType;
  }

  @Override
  public PCollection<KV<String, StrategyState>> expand(PCollection<KV<String, ImmutableList<Candle>>> input) {
    // Split input so that each strategy type is processed individually.
    PCollection<KV<String, StrategyProcessingRequest>> split = input.apply(ParDo.of(optimizeEachStrategyDoFn));

    // Process each strategy type record.
    return split.apply("OptimizeEachStrategy", ParDo.of(optimizeEachStrategyDoFn));
  }
}
