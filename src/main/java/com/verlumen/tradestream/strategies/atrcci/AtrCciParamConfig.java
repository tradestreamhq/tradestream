package com.verlumen.tradestream.strategies.atrcci;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.AtrCciParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public final class AtrCciParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 30), // ATR Period
          ChromosomeSpec.ofInteger(10, 50) // CCI Period
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

    IntegerChromosome atrPeriodChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome cciPeriodChrom = (IntegerChromosome) chromosomes.get(1);

    AtrCciParameters parameters =
        AtrCciParameters.newBuilder()
            .setAtrPeriod(atrPeriodChrom.gene().allele())
            .setCciPeriod(cciPeriodChrom.gene().allele())
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
