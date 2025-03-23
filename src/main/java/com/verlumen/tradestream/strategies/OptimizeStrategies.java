package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;
import com.verlumen.tradestream.marketdata.Candle;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;

/**
 * Composite PTransform that chains the splitting of input records per strategy type
 * with the isolated processing of each strategy type.
 */
final class OptimizeStrategies 
    extends PTransform<PCollection<KV<String, ImmutableList<Candle>>>, 
                      PCollection<KV<String, StrategyState>>> {

    private final SplitByStrategyType splitByStrategyType;
    private final OptimizeEachStrategyDoFn optimizeEachStrategyDoFn;

    @Inject
    OptimizeStrategies(
        SplitByStrategyType splitByStrategyType,
        OptimizeEachStrategyDoFn optimizeEachStrategyDoFn) {
        this.splitByStrategyType = splitByStrategyType;
        this.optimizeEachStrategyDoFn = optimizeEachStrategyDoFn;
    }

    @Override
    public PCollection<KV<String, StrategyState>> expand(PCollection<KV<String, ImmutableList<Candle>>> input) {
        // First, split the input so each record corresponds to a single strategy type.
        PCollection<KV<String, StrategyProcessingRequest>> split =
            input.apply("SplitByStrategyType", splitByStrategyType);
        // Then, process each strategy type record individually without a loop.
        return split.apply("OptimizeEachStrategy", ParDo.of(optimizeEachStrategyDoFn));
    }
}
