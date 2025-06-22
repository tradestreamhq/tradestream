package com.verlumen.tradestream.strategies.volumespreadanalysis;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.VolumeSpreadAnalysisParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

public final class VolumeSpreadAnalysisParamConfig implements ParamConfig {
  private static final Logger logger =
      Logger.getLogger(VolumeSpreadAnalysisParamConfig.class.getName());

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(10, 50)); // volumePeriod

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

    int volumePeriod = getIntegerValue(chromosomes, 0, 20);

    VolumeSpreadAnalysisParameters parameters =
        VolumeSpreadAnalysisParameters.newBuilder().setVolumePeriod(volumePeriod).build();

    return Any.pack(parameters);
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }

  private int getIntegerValue(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes, int index, int defaultValue) {
    try {
      return ((IntegerChromosome) chromosomes.get(index)).intValue();
    } catch (Exception e) {
      logger.warning("Failed to get integer value at index " + index + ": " + e.getMessage());
      return defaultValue;
    }
  }

  private Any getDefaultParameters() {
    return Any.pack(
        VolumeSpreadAnalysisParameters.newBuilder()
            .setVolumePeriod(20)
            .build());
  }
} 