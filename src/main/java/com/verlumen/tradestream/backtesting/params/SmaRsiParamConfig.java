package com.verlumen.tradestream.backtesting.params;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.Range;
import com.google.protobuf.Any;
import io.jenetics.Genotype;
import io.jenetics.IntegerGene;
import com.verlumen.tradestream.strategies.SmaRsiParameters;

/**
 * Parameter configuration for SMA/RSI strategy optimization.
 */
final class SmaRsiParamConfig implements ParamConfig<Integer, IntegerGene> {
    private static final ImmutableList<Range<Integer>> CHROMOSOMES = ImmutableList.of(
        // Moving Average Period (5-50)
        Range.closed(5, 50),
        // RSI Period (2-30)
        Range.closed(2, 30),
        // Overbought Threshold (60-85)
        Range.closed(60, 85),
        // Oversold Threshold (15-40)
        Range.closed(15, 40)
    );

    @Override
    public ImmutableList<Range<Integer>> getChromosomes() {
        return CHROMOSOMES;
    }

    @Override
    public Any createParameters(Genotype<IntegerGene> genotype) {
        return Any.pack(SmaRsiParameters.newBuilder()
            .setMovingAveragePeriod(genotype.get(0).get(0).allele())
            .setRsiPeriod(genotype.get(1).get(0).allele())
            .setOverboughtThreshold(genotype.get(2).get(0).allele())
            .setOversoldThreshold(genotype.get(3).get(0).allele())
            .build());
    }
}
