package com.verlumen.tradestream.strategies.bbandwr;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.BbandWRParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public final class BbandWRParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(10, 50),   // Bollinger Bands Period
          ChromosomeSpec.ofInteger(5, 30),    // Williams %R Period
          ChromosomeSpec.ofDouble(1.5, 3.0)   // Standard Deviation Multiplier
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

    IntegerChromosome bbandsPeriodChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome wrPeriodChrom = (IntegerChromosome) chromosomes.get(1);
    DoubleChromosome stdDevMultiplierChrom = (DoubleChromosome) chromosomes.get(2);

    BbandWRParameters parameters =
        BbandWRParameters.newBuilder()
            .setBbandsPeriod(bbandsPeriodChrom.gene().allele())
            .setWrPeriod(wrPeriodChrom.gene().allele())
            .setStdDevMultiplier(stdDevMultiplierChrom.gene().allele())
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
