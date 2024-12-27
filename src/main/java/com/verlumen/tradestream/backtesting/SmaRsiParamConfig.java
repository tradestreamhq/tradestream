package com.verlumen.tradestream.backtesting;

import com.google.common.collect.ImmutableList;
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
        ParamRange.create(5, 50),
        // RSI Period (2-30)
        ParamRange.create(2, 30),
        // Overbought Threshold (60-85)
        ParamRange.create(60, 85),
        // Oversold Threshold (15-40)
        ParamRange.create(15, 40)
    );

    @Override
    public ImmutableList<ParamRange> getChromosomes() {
        return CHROMOSOMES;
    }

    @Override
    public Any createParameters(Genotype<DoubleGene> genotype) {
        return Any.pack(SmaRsiParameters.newBuilder()
            .setMovingAveragePeriod((int) genotype.get(0).get(0).allele())
            .setRsiPeriod((int) genotype.get(1).get(0).allele())
            .setOverboughtThreshold(genotype.get(2).get(0).allele())
            .setOversoldThreshold(genotype.get(3).get(0).allele())
            .build());
    }
}
