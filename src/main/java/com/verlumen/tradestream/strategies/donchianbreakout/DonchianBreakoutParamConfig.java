package com.verlumen.tradestream.strategies.donchianbreakout;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.DonchianBreakoutParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public final class DonchianBreakoutParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(10, 50) // Donchian Period
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

    IntegerChromosome donchianPeriodChrom = (IntegerChromosome) chromosomes.get(0);

    DonchianBreakoutParameters parameters =
        DonchianBreakoutParameters.newBuilder()
            .setDonchianPeriod(donchianPeriodChrom.gene().allele())
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
    return StrategyType.DONCHIAN_BREAKOUT;
  }
}
