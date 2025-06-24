package com.verlumen.tradestream.strategies.regressionchannel;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.RegressionChannelParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

public final class RegressionChannelParamConfig implements ParamConfig {
  private static final Logger logger =
      Logger.getLogger(RegressionChannelParamConfig.class.getName());

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(10, 100) // period
          );

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    try {
      if (chromosomes.size() != SPECS.size()) {
        logger.warning("Expected " + SPECS.size() + " chromosomes but got " + chromosomes.size());
        return getDefaultParameters();
      }
      int period = getIntegerValue(chromosomes, 0, 20);
      return Any.pack(RegressionChannelParameters.newBuilder().setPeriod(period).build());
    } catch (Exception e) {
      logger.warning("Error creating parameters: " + e.getMessage());
      return getDefaultParameters();
    }
  }

  private Any getDefaultParameters() {
    return Any.pack(RegressionChannelParameters.newBuilder().setPeriod(20).build());
  }

  private int getIntegerValue(
      ImmutableList<? extends NumericChromosome<?, ?>> chromosomes, int index, int defaultValue) {
    try {
      if (index >= chromosomes.size()) return defaultValue;
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
