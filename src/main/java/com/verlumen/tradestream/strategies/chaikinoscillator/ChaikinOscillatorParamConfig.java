package com.verlumen.tradestream.strategies.chaikinoscillator;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.ChaikinOscillatorParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public class ChaikinOscillatorParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(2, 20), // Fast Period
          ChromosomeSpec.ofInteger(5, 50) // Slow Period
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

    IntegerChromosome fastPeriodChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome slowPeriodChrom = (IntegerChromosome) chromosomes.get(1);

    ChaikinOscillatorParameters parameters =
        ChaikinOscillatorParameters.newBuilder()
            .setFastPeriod(fastPeriodChrom.gene().allele())
            .setSlowPeriod(slowPeriodChrom.gene().allele())
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
