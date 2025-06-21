package com.verlumen.tradestream.strategies.doubleemacrossover;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public final class DoubleEmaCrossoverParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(2, 30), // Short EMA Period
          ChromosomeSpec.ofInteger(10, 100) // Long EMA Period
          );

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    if (chromosomes.size() != SPECS.size()) {
      throw new IllegalArgumentException(
          "Expected " + SPECS.size() + " chromosomes but got " + chromosomes.size());
    }

    IntegerChromosome shortEmaPeriodChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome longEmaPeriodChrom = (IntegerChromosome) chromosomes.get(1);

    DoubleEmaCrossoverParameters parameters =
        DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(shortEmaPeriodChrom.gene().allele())
            .setLongEmaPeriod(longEmaPeriodChrom.gene().allele())
            .build();

    return Any.pack(parameters);
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }
}
