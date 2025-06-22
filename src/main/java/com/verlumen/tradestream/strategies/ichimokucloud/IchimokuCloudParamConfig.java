package com.verlumen.tradestream.strategies.ichimokucloud;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.IchimokuCloudParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public final class IchimokuCloudParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 20),   // tenkanSenPeriod
          ChromosomeSpec.ofInteger(20, 60),  // kijunSenPeriod
          ChromosomeSpec.ofInteger(50, 200), // senkouSpanBPeriod
          ChromosomeSpec.ofInteger(20, 60)   // chikouSpanPeriod
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

    IntegerChromosome tenkanSenPeriodChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome kijunSenPeriodChrom = (IntegerChromosome) chromosomes.get(1);
    IntegerChromosome senkouSpanBPeriodChrom = (IntegerChromosome) chromosomes.get(2);
    IntegerChromosome chikouSpanPeriodChrom = (IntegerChromosome) chromosomes.get(3);

    IchimokuCloudParameters parameters =
        IchimokuCloudParameters.newBuilder()
            .setTenkanSenPeriod(tenkanSenPeriodChrom.gene().allele())
            .setKijunSenPeriod(kijunSenPeriodChrom.gene().allele())
            .setSenkouSpanBPeriod(senkouSpanBPeriodChrom.gene().allele())
            .setChikouSpanPeriod(chikouSpanPeriodChrom.gene().allele())
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
