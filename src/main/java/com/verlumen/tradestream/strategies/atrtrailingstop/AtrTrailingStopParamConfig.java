package com.verlumen.tradestream.strategies.atrtrailingstop;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.AtrTrailingStopParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public final class AtrTrailingStopParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 30), // ATR Period
          ChromosomeSpec.ofDouble(1.0, 5.0) // Multiplier
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
    DoubleChromosome multiplierChrom = (DoubleChromosome) chromosomes.get(1);

    AtrTrailingStopParameters parameters =
        AtrTrailingStopParameters.newBuilder()
            .setAtrPeriod(atrPeriodChrom.gene().allele())
            .setMultiplier(multiplierChrom.gene().allele())
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
