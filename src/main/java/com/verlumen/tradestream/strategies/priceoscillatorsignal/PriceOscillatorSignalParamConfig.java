package com.verlumen.tradestream.strategies.priceoscillatorsignal;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.PriceOscillatorSignalParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

public final class PriceOscillatorSignalParamConfig implements ParamConfig {
  private static final Logger logger =
      Logger.getLogger(PriceOscillatorSignalParamConfig.class.getName());

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 20), // fastPeriod
          ChromosomeSpec.ofInteger(10, 50), // slowPeriod
          ChromosomeSpec.ofInteger(5, 20) // signalPeriod
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
      PriceOscillatorSignalParameters parameters =
          PriceOscillatorSignalParameters.newBuilder()
              .setFastPeriod(((IntegerChromosome) chromosomes.get(0)).intValue())
              .setSlowPeriod(((IntegerChromosome) chromosomes.get(1)).intValue())
              .setSignalPeriod(((IntegerChromosome) chromosomes.get(2)).intValue())
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

  private PriceOscillatorSignalParameters getDefaultParameters() {
    return PriceOscillatorSignalParameters.newBuilder()
        .setFastPeriod(10)
        .setSlowPeriod(20)
        .setSignalPeriod(9)
        .build();
  }
}
