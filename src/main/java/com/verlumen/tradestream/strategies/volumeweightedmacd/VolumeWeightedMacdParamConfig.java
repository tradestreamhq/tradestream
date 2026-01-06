package com.verlumen.tradestream.strategies.volumeweightedmacd;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.VolumeWeightedMacdParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

/**
 * Parameter configuration for the Volume Weighted MACD strategy.
 *
 * <p>This strategy combines volume into MACD calculations by using VWAP and volume-weighted EMAs to
 * create a more volume-sensitive MACD indicator. It enters when the MACD line crosses above the
 * signal line, and exits when the MACD line crosses below the signal line.
 */
public class VolumeWeightedMacdParamConfig implements ParamConfig {

  private static final int DEFAULT_SHORT_PERIOD = 12;
  private static final int DEFAULT_LONG_PERIOD = 26;
  private static final int DEFAULT_SIGNAL_PERIOD = 9;

  private static final Logger logger =
      Logger.getLogger(VolumeWeightedMacdParamConfig.class.getName());

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 20), // Short Period
          ChromosomeSpec.ofInteger(15, 50), // Long Period
          ChromosomeSpec.ofInteger(5, 15) // Signal Period
          );

  public Any getDefaultParameters() {
    return Any.pack(
        VolumeWeightedMacdParameters.newBuilder()
            .setShortPeriod(DEFAULT_SHORT_PERIOD)
            .setLongPeriod(DEFAULT_LONG_PERIOD)
            .setSignalPeriod(DEFAULT_SIGNAL_PERIOD)
            .build());
  }

  public VolumeWeightedMacdParameters unpack(Any parameters) throws InvalidProtocolBufferException {
    return parameters.unpack(VolumeWeightedMacdParameters.class);
  }

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
                + " - Using default values for Volume Weighted MACD parameters");

        return getDefaultParameters();
      }

      int shortPeriod = getIntegerValue(chromosomes, 0, DEFAULT_SHORT_PERIOD);
      int longPeriod = getIntegerValue(chromosomes, 1, DEFAULT_LONG_PERIOD);
      int signalPeriod = getIntegerValue(chromosomes, 2, DEFAULT_SIGNAL_PERIOD);

      VolumeWeightedMacdParameters parameters =
          VolumeWeightedMacdParameters.newBuilder()
              .setShortPeriod(shortPeriod)
              .setLongPeriod(longPeriod)
              .setSignalPeriod(signalPeriod)
              .build();

      return Any.pack(parameters);
    } catch (Exception e) {
      logger.warning(
          "Error creating Volume Weighted MACD parameters: "
              + e.getMessage()
              + " - Using default values");

      return getDefaultParameters();
    }
  }

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
