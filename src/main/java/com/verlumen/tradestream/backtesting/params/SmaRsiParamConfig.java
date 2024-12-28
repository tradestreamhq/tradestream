package com.verlumen.tradestream.backtesting.params;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import io.jenetics.Gene;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import com.verlumen.tradestream.strategies.SmaRsiParameters;

/**
 * Parameter configuration for SMA/RSI strategy with proper integer and double parameters.
 */
public final class SmaRsiParamConfig implements MixedParamConfig {
    private static final ImmutableList<ChromosomeSpec<?>> SPECS = ImmutableList.of(
        // Integer parameters
        ChromosomeSpec.ofInteger(5, 50),    // Moving Average Period
        ChromosomeSpec.ofInteger(2, 30),    // RSI Period
        // Double parameters
        ChromosomeSpec.ofDouble(60.0, 85.0), // Overbought Threshold
        ChromosomeSpec.ofDouble(15.0, 40.0)  // Oversold Threshold
    );

    @Override
    public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
        return SPECS;
    }

    @Override
    public Any createParameters(ImmutableList<? extends NumericChromosome<? extends Gene<?, ?>>> chromosomes) {
        if (chromosomes.size() != SPECS.size()) {
            throw new IllegalArgumentException(
                "Expected " + SPECS.size() + " chromosomes but got " + chromosomes.size());
        }

        // Extract parameters with proper typing
        int maPeriod = ((IntegerChromosome)chromosomes.get(0)).getGene().allele();
        int rsiPeriod = ((IntegerChromosome)chromosomes.get(1)).getGene().allele();
        double overbought = ((DoubleChromosome)chromosomes.get(2)).getGene().allele();
        double oversold = ((DoubleChromosome)chromosomes.get(3)).getGene().allele();

        // Build parameters
        SmaRsiParameters parameters = SmaRsiParameters.newBuilder()
            .setMovingAveragePeriod(maPeriod)
            .setRsiPeriod(rsiPeriod)
            .setOverboughtThreshold(overbought)
            .setOversoldThreshold(oversold)
            .build();

        return Any.pack(parameters);
    }

    @Override
    public ImmutableList<? extends NumericChromosome<? extends Gene<?, ?>>> initialChromosomes() {
        return SPECS.stream()
            .map(ChromosomeSpec::createChromosome)
            .collect(ImmutableList.toImmutableList());
    }
}
