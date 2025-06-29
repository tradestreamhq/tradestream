package com.verlumen.tradestream.strategies.variableperiodema;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.VariablePeriodEmaParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public final class VariablePeriodEmaParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 50), // minPeriod
          ChromosomeSpec.ofInteger(10, 100) // maxPeriod
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
    IntegerChromosome minPeriodChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome maxPeriodChrom = (IntegerChromosome) chromosomes.get(1);
    VariablePeriodEmaParameters parameters =
        VariablePeriodEmaParameters.newBuilder()
            .setMinPeriod(minPeriodChrom.gene().allele())
            .setMaxPeriod(maxPeriodChrom.gene().allele())
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
