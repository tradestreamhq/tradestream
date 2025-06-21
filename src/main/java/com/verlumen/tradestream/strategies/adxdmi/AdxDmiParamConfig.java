package com.verlumen.tradestream.strategies.adxdmi;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.AdxDmiParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public class AdxDmiParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(10, 30), // ADX Period
          ChromosomeSpec.ofInteger(10, 30) // DI Period
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

    IntegerChromosome adxPeriodChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome diPeriodChrom = (IntegerChromosome) chromosomes.get(1);

    AdxDmiParameters parameters =
        AdxDmiParameters.newBuilder()
            .setAdxPeriod(adxPeriodChrom.gene().allele())
            .setDiPeriod(diPeriodChrom.gene().allele())
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
