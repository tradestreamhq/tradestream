package com.verlumen.tradestream.strategies.cmomfi;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.CmoMfiParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

public final class CmoMfiParamConfig implements ParamConfig {
  private static final Logger logger = Logger.getLogger(CmoMfiParamConfig.class.getName());

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(10, 30), // cmoPeriod
          ChromosomeSpec.ofInteger(10, 30)); // mfiPeriod

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    if (chromosomes.size() != 2) {
      logger.warning("Expected 2 chromosomes but got " + chromosomes.size());
      return getDefaultParameters();
    }

    int cmoPeriod = getIntegerValue(chromosomes, 0, 14);
    int mfiPeriod = getIntegerValue(chromosomes, 1, 14);

    CmoMfiParameters parameters =
        CmoMfiParameters.newBuilder().setCmoPeriod(cmoPeriod).setMfiPeriod(mfiPeriod).build();

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
    return Any.pack(CmoMfiParameters.newBuilder().setCmoPeriod(14).setMfiPeriod(14).build());
  }
}
