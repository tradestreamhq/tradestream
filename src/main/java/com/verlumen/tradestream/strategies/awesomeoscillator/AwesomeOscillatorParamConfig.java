package com.verlumen.tradestream.strategies.awesomeoscillator;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.AwesomeOscillatorParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public class AwesomeOscillatorParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(2, 20), // Short Period
          ChromosomeSpec.ofInteger(10, 50) // Long Period
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

    IntegerChromosome shortPeriodChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome longPeriodChrom = (IntegerChromosome) chromosomes.get(1);

    AwesomeOscillatorParameters parameters =
        AwesomeOscillatorParameters.newBuilder()
            .setShortPeriod(shortPeriodChrom.gene().allele())
            .setLongPeriod(longPeriodChrom.gene().allele())
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
