package com.verlumen.tradestream.strategies.vwapcrossover;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.VwapCrossoverParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public final class VwapCrossoverParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(10, 50), // VWAP Period
          ChromosomeSpec.ofInteger(10, 50)  // Moving Average Period
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

    IntegerChromosome vwapPeriodChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome maPeriodChrom = (IntegerChromosome) chromosomes.get(1);

    VwapCrossoverParameters parameters =
        VwapCrossoverParameters.newBuilder()
            .setVwapPeriod(vwapPeriodChrom.gene().allele())
            .setMovingAveragePeriod(maPeriodChrom.gene().allele())
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
