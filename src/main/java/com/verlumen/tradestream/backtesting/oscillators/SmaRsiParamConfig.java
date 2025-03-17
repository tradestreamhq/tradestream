package com.verlumen.tradestream.backtesting.oscillators;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.backtesting.ChromosomeSpec;
import com.verlumen.tradestream.backtesting.ParamConfig;
import com.verlumen.tradestream.strategies.SmaRsiParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.IntegerChromosome;
import io.jenetics.DoubleChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

final class SmaRsiParamConfig implements ParamConfig {
    private static final Logger logger = Logger.getLogger(SmaRsiParamConfig.class.getName());

    private static final ImmutableList<ChromosomeSpec<?>> SPECS = ImmutableList.of(
        // Integer parameters
        ChromosomeSpec.ofInteger(5, 50),    // Moving Average Period
        ChromosomeSpec.ofInteger(2, 30),    // RSI Period
        // Double parameters
        ChromosomeSpec.ofDouble(60.0, 85.0), // Overbought Threshold
        ChromosomeSpec.ofDouble(15.0, 40.0)  // Oversold Threshold
    );

    static SmaRsiParamConfig create() {
        return new SmaRsiParamConfig();
    }

    private SmaRsiParamConfig() {}
    
    @Override
    public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
        return SPECS;
    }

    @Override
    public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
        try {
            if (chromosomes.size() != SPECS.size()) {
                logger.warning("Expected " + SPECS.size() + " chromosomes but got " + chromosomes.size() + 
                    " - Using default values for SMA-RSI parameters");
                
                // Create default parameters rather than throwing exception
                return Any.pack(SmaRsiParameters.newBuilder()
                    .setMovingAveragePeriod(20)
                    .setRsiPeriod(14)
                    .setOverboughtThreshold(70.0)
                    .setOversoldThreshold(30.0)
                    .build());
            }

            // Extract parameters with proper casting
            // Use safe access methods for chromosomes
            int maPeriod = getIntegerValue(chromosomes, 0, 20);
            int rsiPeriod = getIntegerValue(chromosomes, 1, 14);
            double overboughtThreshold = getDoubleValue(chromosomes, 2, 70.0);
            double oversoldThreshold = getDoubleValue(chromosomes, 3, 30.0);

            // Build parameters
            SmaRsiParameters parameters = SmaRsiParameters.newBuilder()
                .setMovingAveragePeriod(maPeriod)
                .setRsiPeriod(rsiPeriod)
                .setOverboughtThreshold(overboughtThreshold)
                .setOversoldThreshold(oversoldThreshold)
                .build();

            return Any.pack(parameters);
        } catch (Exception e) {
            logger.warning("Error creating SMA-RSI parameters: " + e.getMessage() + 
                " - Using default values");
            
            // Create default parameters on any error
            return Any.pack(SmaRsiParameters.newBuilder()
                .setMovingAveragePeriod(20)
                .setRsiPeriod(14)
                .setOverboughtThreshold(70.0)
                .setOversoldThreshold(30.0)
                .build());
        }
    }
    
    // Helper method to safely get integer values from chromosomes
    private int getIntegerValue(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes, 
                               int index, int defaultValue) {
        try {
            if (index >= chromosomes.size()) {
                return defaultValue;
            }
            
            NumericChromosome<?, ?> chromosome = chromosomes.get(index);
            if (chromosome instanceof IntegerChromosome) {
                return ((IntegerChromosome) chromosome).gene().intValue();
            } else {
                // Try to convert from other numeric types
                return (int) chromosome.gene().doubleValue();
            }
        } catch (Exception e) {
            return defaultValue;
        }
    }
    
    // Helper method to safely get double values from chromosomes
    private double getDoubleValue(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes, 
                                 int index, double defaultValue) {
        try {
            if (index >= chromosomes.size()) {
                return defaultValue;
            }
            
            NumericChromosome<?, ?> chromosome = chromosomes.get(index);
            return chromosome.gene().doubleValue();
        } catch (Exception e) {
            return defaultValue;
        }
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
