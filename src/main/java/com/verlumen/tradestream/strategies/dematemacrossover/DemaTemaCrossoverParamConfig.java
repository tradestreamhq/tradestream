package com.verlumen.tradestream.strategies.dematemacrossover;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.DemaTemaCrossoverParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public final class DemaTemaCrossoverParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 50), // demaPeriod
          ChromosomeSpec.ofInteger(5, 50) // temaPeriod
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

    IntegerChromosome demaPeriodChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome temaPeriodChrom = (IntegerChromosome) chromosomes.get(1);

    DemaTemaCrossoverParameters parameters =
        DemaTemaCrossoverParameters.newBuilder()
            .setDemaPeriod(demaPeriodChrom.gene().allele())
            .setTemaPeriod(temaPeriodChrom.gene().allele())
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
