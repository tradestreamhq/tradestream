package com.verlumen.tradestream.strategies.sarmfi;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.SarMfiParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public final class SarMfiParamConfig implements ParamConfig {
  private static final double MIN_AF_START = 0.01;
  private static final double MAX_AF_START = 0.2;
  private static final double MIN_AF_INCREMENT = 0.01;
  private static final double MAX_AF_INCREMENT = 0.2;
  private static final double MIN_AF_MAX = 0.1;
  private static final double MAX_AF_MAX = 1.0;
  private static final int MIN_MFI_PERIOD = 2;
  private static final int MAX_MFI_PERIOD = 100;
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofDouble(MIN_AF_START, MAX_AF_START),
          ChromosomeSpec.ofDouble(MIN_AF_INCREMENT, MAX_AF_INCREMENT),
          ChromosomeSpec.ofDouble(MIN_AF_MAX, MAX_AF_MAX),
          ChromosomeSpec.ofInteger(MIN_MFI_PERIOD, MAX_MFI_PERIOD));

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    double afStart = MIN_AF_START;
    double afIncrement = MIN_AF_INCREMENT;
    double afMax = MIN_AF_MAX;
    int mfiPeriod = MIN_MFI_PERIOD;
    if (chromosomes != null && chromosomes.size() == 4) {
      afStart = ((DoubleChromosome) chromosomes.get(0)).doubleValue();
      afIncrement = ((DoubleChromosome) chromosomes.get(1)).doubleValue();
      afMax = ((DoubleChromosome) chromosomes.get(2)).doubleValue();
      mfiPeriod = ((IntegerChromosome) chromosomes.get(3)).intValue();
    }
    return Any.pack(
        SarMfiParameters.newBuilder()
            .setAccelerationFactorStart(afStart)
            .setAccelerationFactorIncrement(afIncrement)
            .setAccelerationFactorMax(afMax)
            .setMfiPeriod(mfiPeriod)
            .build());
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }
}
