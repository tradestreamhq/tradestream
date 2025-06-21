package com.verlumen.tradestream.strategies.momentumsmacrossover;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.MomentumSmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public final class MomentumSmaCrossoverParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 30), // Momentum Period
          ChromosomeSpec.ofInteger(5, 50) // SMA Period
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

    IntegerChromosome momentumPeriodChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome smaPeriodChrom = (IntegerChromosome) chromosomes.get(1);

    MomentumSmaCrossoverParameters parameters =
        MomentumSmaCrossoverParameters.newBuilder()
            .setMomentumPeriod(momentumPeriodChrom.gene().allele())
            .setSmaPeriod(smaPeriodChrom.gene().allele())
            .build();

    return Any.pack(parameters);
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.MOMENTUM_SMA_CROSSOVER;
  }
}
