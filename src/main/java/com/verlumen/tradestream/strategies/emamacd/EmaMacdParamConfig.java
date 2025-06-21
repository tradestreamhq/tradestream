package com.verlumen.tradestream.strategies.emamacd;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.EmaMacdParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public final class EmaMacdParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          // Integer parameters
          ChromosomeSpec.ofInteger(2, 20), // Short EMA Period
          ChromosomeSpec.ofInteger(10, 50), // Long EMA Period
          ChromosomeSpec.ofInteger(5, 20) // Signal Period
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

    // Extract parameters with proper casting
    IntegerChromosome shortEmaPeriodChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome longEmaPeriodChrom = (IntegerChromosome) chromosomes.get(1);
    IntegerChromosome signalPeriodChrom = (IntegerChromosome) chromosomes.get(2);

    // Build parameters
    EmaMacdParameters parameters =
        EmaMacdParameters.newBuilder()
            .setShortEmaPeriod(shortEmaPeriodChrom.gene().allele())
            .setLongEmaPeriod(longEmaPeriodChrom.gene().allele())
            .setSignalPeriod(signalPeriodChrom.gene().allele())
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
