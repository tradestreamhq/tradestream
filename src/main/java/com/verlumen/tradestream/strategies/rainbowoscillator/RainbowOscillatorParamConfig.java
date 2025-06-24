package com.verlumen.tradestream.strategies.rainbowoscillator;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.RainbowOscillatorParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

public final class RainbowOscillatorParamConfig implements ParamConfig {
  private static final Logger logger =
      Logger.getLogger(RainbowOscillatorParamConfig.class.getName());

  // For simplicity, we'll use 3 periods: short, medium, long
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 20), // short period
          ChromosomeSpec.ofInteger(10, 50), // medium period
          ChromosomeSpec.ofInteger(20, 100) // long period
          );

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    if (chromosomes.size() != 3) {
      logger.warning("Expected 3 chromosomes but got " + chromosomes.size());
      return Any.pack(getDefaultParameters());
    }

    try {
      RainbowOscillatorParameters parameters =
          RainbowOscillatorParameters.newBuilder()
              .addPeriods(((IntegerChromosome) chromosomes.get(0)).intValue())
              .addPeriods(((IntegerChromosome) chromosomes.get(1)).intValue())
              .addPeriods(((IntegerChromosome) chromosomes.get(2)).intValue())
              .build();

      return Any.pack(parameters);
    } catch (Exception e) {
      logger.warning("Error creating parameters: " + e.getMessage());
      return Any.pack(getDefaultParameters());
    }
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }

  private RainbowOscillatorParameters getDefaultParameters() {
    return RainbowOscillatorParameters.newBuilder()
        .addPeriods(10)
        .addPeriods(20)
        .addPeriods(50)
        .build();
  }
}
