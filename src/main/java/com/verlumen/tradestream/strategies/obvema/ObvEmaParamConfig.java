package com.verlumen.tradestream.strategies.obvema;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.ObvEmaParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

public final class ObvEmaParamConfig implements ParamConfig {
  private static final Logger logger = Logger.getLogger(ObvEmaParamConfig.class.getName());

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(ChromosomeSpec.ofInteger(10, 50)); // emaPeriod

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    if (chromosomes.size() != 1) {
      logger.warning("Expected 1 chromosome but got " + chromosomes.size());
    }

    int emaPeriod = getIntegerValue(chromosomes, 0, 20);

    ObvEmaParameters parameters = ObvEmaParameters.newBuilder().setEmaPeriod(emaPeriod).build();

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
      if (index < chromosomes.size()) {
        IntegerChromosome chromosome = (IntegerChromosome) chromosomes.get(index);
        return chromosome.gene().allele();
      }
    } catch (Exception e) {
      logger.warning("Error getting integer value at index " + index + ": " + e.getMessage());
    }
    return defaultValue;
  }

  private Any getDefaultParameters() {
    return Any.pack(ObvEmaParameters.newBuilder().setEmaPeriod(20).build());
  }
}
