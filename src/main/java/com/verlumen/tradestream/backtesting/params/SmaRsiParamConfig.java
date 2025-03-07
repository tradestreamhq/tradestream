package com.verlumen.tradestream.backtesting.params;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.backtesting.ChromosomeSpec;
import com.verlumen.tradestream.strategies.SmaRsiParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.IntegerChromosome;
import io.jenetics.DoubleChromosome;
import io.jenetics.NumericChromosome;

final class SmaRsiParamConfig implements ParamConfig {
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
    public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
        if (chromosomes.size() != SPECS.size()) {
            throw new IllegalArgumentException(
                "Expected " + SPECS.size() + " chromosomes but got " + chromosomes.size());
        }

        // Extract parameters with proper casting
        IntegerChromosome maPeriodChrom = (IntegerChromosome) chromosomes.get(0);
        IntegerChromosome rsiPeriodChrom = (IntegerChromosome) chromosomes.get(1);
        DoubleChromosome overboughtChrom = (DoubleChromosome) chromosomes.get(2);
        DoubleChromosome oversoldChrom = (DoubleChromosome) chromosomes.get(3);

        // Build parameters
        SmaRsiParameters parameters = SmaRsiParameters.newBuilder()
            .setMovingAveragePeriod(maPeriodChrom.gene().allele())
            .setRsiPeriod(rsiPeriodChrom.gene().allele())
            .setOverboughtThreshold(overboughtChrom.gene().allele())
            .setOversoldThreshold(oversoldChrom.gene().allele())
            .build();

        return Any.pack(parameters);
    }

    @Override
    public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
        return SPECS.stream()
            .map(ChromosomeSpec::createChromosome)
            .collect(ImmutableList.toImmutableList());
    }

    @Override
    public StrategyType getStrategyType() {
        return StrategyType.SMA_RSI;
    }
}
