package com.verlumen.tradestream.strategies.parabolicsarr;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.ParabolicSarParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.DoubleChromosome;
import io.jenetics.NumericChromosome;

public final class ParabolicSarParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofDouble(0.01, 0.05), // Acceleration Factor Start
          ChromosomeSpec.ofDouble(0.01, 0.05), // Acceleration Factor Increment
          ChromosomeSpec.ofDouble(0.1, 0.5) // Acceleration Factor Max
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

    DoubleChromosome afStartChrom = (DoubleChromosome) chromosomes.get(0);
    DoubleChromosome afIncrementChrom = (DoubleChromosome) chromosomes.get(1);
    DoubleChromosome afMaxChrom = (DoubleChromosome) chromosomes.get(2);

    double afStart = afStartChrom.gene().allele();
    double afIncrement = afIncrementChrom.gene().allele();
    double afMax = afMaxChrom.gene().allele();

    // Ensure max >= start
    if (afMax < afStart) {
      afMax = afStart;
    }

    ParabolicSarParameters parameters =
        ParabolicSarParameters.newBuilder()
            .setAccelerationFactorStart(afStart)
            .setAccelerationFactorIncrement(afIncrement)
            .setAccelerationFactorMax(afMax)
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
