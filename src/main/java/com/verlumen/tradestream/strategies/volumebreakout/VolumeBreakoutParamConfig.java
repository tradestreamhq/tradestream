package com.verlumen.tradestream.strategies.volumebreakout;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.VolumeBreakoutParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

public final class VolumeBreakoutParamConfig implements ParamConfig {
  private static final Logger logger = Logger.getLogger(VolumeBreakoutParamConfig.class.getName());

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(ChromosomeSpec.ofDouble(1.5, 3.0)); // volumeMultiplier

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    if (chromosomes.size() != 1) {
      logger.warning("Expected 1 chromosome but got " + chromosomes.size());
      return getDefaultParameters();
    }

    double volumeMultiplier = getDoubleValue(chromosomes, 0, 2.0);

    VolumeBreakoutParameters parameters =
        VolumeBreakoutParameters.newBuilder().setVolumeMultiplier(volumeMultiplier).build();

    return Any.pack(parameters);
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }

  private double getDoubleValue(
      ImmutableList<? extends NumericChromosome<?, ?>> chromosomes,
      int index,
      double defaultValue) {
    try {
      return ((DoubleChromosome) chromosomes.get(index)).doubleValue();
    } catch (Exception e) {
      logger.warning("Failed to get double value at index " + index + ": " + e.getMessage());
      return defaultValue;
    }
  }

  private Any getDefaultParameters() {
    return Any.pack(VolumeBreakoutParameters.newBuilder().setVolumeMultiplier(2.0).build());
  }
}
