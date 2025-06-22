package com.verlumen.tradestream.strategies.klingervolume;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.KlingerVolumeParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

public final class KlingerVolumeParamConfig implements ParamConfig {
  private static final Logger logger = Logger.getLogger(KlingerVolumeParamConfig.class.getName());

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 15), // shortPeriod
          ChromosomeSpec.ofInteger(20, 50), // longPeriod
          ChromosomeSpec.ofInteger(5, 15)); // signalPeriod

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    if (chromosomes.size() != 3) {
      logger.warning("Expected 3 chromosomes but got " + chromosomes.size());
      return getDefaultParameters();
    }

    int shortPeriod = getIntegerValue(chromosomes, 0, 10);
    int longPeriod = getIntegerValue(chromosomes, 1, 35);
    int signalPeriod = getIntegerValue(chromosomes, 2, 10);

    KlingerVolumeParameters parameters =
        KlingerVolumeParameters.newBuilder()
            .setShortPeriod(shortPeriod)
            .setLongPeriod(longPeriod)
            .setSignalPeriod(signalPeriod)
            .build();

    return Any.pack(parameters);
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }

  private int getIntegerValue(
      ImmutableList<? extends NumericChromosome<?, ?>> chromosomes, int index, int defaultValue) {
    try {
      return ((IntegerChromosome) chromosomes.get(index)).intValue();
    } catch (Exception e) {
      logger.warning("Failed to get integer value at index " + index + ": " + e.getMessage());
      return defaultValue;
    }
  }

  private Any getDefaultParameters() {
    return Any.pack(
        KlingerVolumeParameters.newBuilder()
            .setShortPeriod(10)
            .setLongPeriod(35)
            .setSignalPeriod(10)
            .build());
  }
}
