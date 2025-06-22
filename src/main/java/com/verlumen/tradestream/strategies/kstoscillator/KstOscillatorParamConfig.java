package com.verlumen.tradestream.strategies.kstoscillator;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.KstOscillatorParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

/**
 * Configuration for KST Oscillator strategy parameters.
 *
 * <p>The KST Oscillator uses different Rate of Change (ROC) periods with different smoothing.
 * It combines four ROC indicators with different periods and smoothing to create a comprehensive
 * momentum indicator.
 */
public final class KstOscillatorParamConfig implements ParamConfig {
  private static final Logger logger = Logger.getLogger(KstOscillatorParamConfig.class.getName());

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          // Integer parameters for RMA periods
          ChromosomeSpec.ofInteger(5, 20),  // RMA1 Period
          ChromosomeSpec.ofInteger(10, 25), // RMA2 Period
          ChromosomeSpec.ofInteger(15, 30), // RMA3 Period
          ChromosomeSpec.ofInteger(20, 40), // RMA4 Period
          ChromosomeSpec.ofInteger(5, 15)   // Signal Period
          );

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    try {
      if (chromosomes.size() != SPECS.size()) {
        logger.warning(
            "Expected "
                + SPECS.size()
                + " chromosomes but got "
                + chromosomes.size()
                + " - Using default values for KST Oscillator parameters");

        // Create default parameters rather than throwing exception
        return Any.pack(
            KstOscillatorParameters.newBuilder()
                .setRma1Period(10)
                .setRma2Period(15)
                .setRma3Period(20)
                .setRma4Period(30)
                .setSignalPeriod(9)
                .build());
      }

      // Extract parameters with proper casting
      int rma1Period = getIntegerValue(chromosomes, 0, 10);
      int rma2Period = getIntegerValue(chromosomes, 1, 15);
      int rma3Period = getIntegerValue(chromosomes, 2, 20);
      int rma4Period = getIntegerValue(chromosomes, 3, 30);
      int signalPeriod = getIntegerValue(chromosomes, 4, 9);

      // Build parameters
      KstOscillatorParameters parameters =
          KstOscillatorParameters.newBuilder()
              .setRma1Period(rma1Period)
              .setRma2Period(rma2Period)
              .setRma3Period(rma3Period)
              .setRma4Period(rma4Period)
              .setSignalPeriod(signalPeriod)
              .build();

      return Any.pack(parameters);
    } catch (Exception e) {
      logger.warning(
          "Error creating KST Oscillator parameters: " + e.getMessage() + " - Using default values");

      // Create default parameters on any error
      return Any.pack(
          KstOscillatorParameters.newBuilder()
              .setRma1Period(10)
              .setRma2Period(15)
              .setRma3Period(20)
              .setRma4Period(30)
              .setSignalPeriod(9)
              .build());
    }
  }

  // Helper method to safely get integer values from chromosomes
  private int getIntegerValue(
      ImmutableList<? extends NumericChromosome<?, ?>> chromosomes, int index, int defaultValue) {
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

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }
} 