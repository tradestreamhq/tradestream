package com.verlumen.tradestream.backtesting;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.Range;
import com.google.protobuf.Any;
import io.jenetics.Genotype;
import io.jenetics.DoubleGene;
import com.verlumen.tradestream.strategies.SmaRsiParameters;

/**
 * Parameter configuration for SMA/RSI strategy optimization.
 */
final class SmaRsiParamConfig implements ParamConfig {
    private static final ImmutableList<ParamRange> CHROMOSOMES = ImmutableList.of(
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
    public ImmutableList<ParamRange> getChromosomes() {
        return CHROMOSOMES;
    }

    @Override
    public Any createParameters(Genotype<DoubleGene> genotype) {
        return Any.pack(SmaRsiParameters.newBuilder()
            .setMovingAveragePeriod(getGenotypeIntValue(genotype, 0))
            .setRsiPeriod(getGenotypeIntValue(genotype, 1))
            .setOverboughtThreshold(getGenotypeIntValue(genotype, 2))
            .setOversoldThreshold(getGenotypeIntValue(genotype, 3))
            .build());
    }

    private int getGenotypeIntValue(Genotype<DoubleGene> genotype, int index) {
        return genotype.get(index).get(0).allele().intValue();
    }
}
