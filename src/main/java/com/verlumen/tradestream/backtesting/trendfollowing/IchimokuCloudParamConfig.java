package com.verlumen.tradestream.backtesting.trendfollowing;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.backtesting.ChromosomeSpec;
import com.verlumen.tradestream.backtesting.ParamConfig;
import com.verlumen.tradestream.strategies.IchimokuCloudParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

final class IchimokuCloudParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 30), // tenkanSenPeriod
          ChromosomeSpec.ofInteger(10, 60), // kijunSenPeriod
          ChromosomeSpec.ofInteger(20, 120), // senkouSpanBPeriod
          ChromosomeSpec.ofInteger(10, 60) // chikouSpanPeriod
          );

  static IchimokuCloudParamConfig create() {
    return new IchimokuCloudParamConfig();
  }

  private IchimokuCloudParamConfig() {}

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    if (chromosomes.size() != SPECS.size()) {
        throw new IllegalArgumentException("Expected " + SPECS.size() + " chromosomes, but got " + chromosomes.size());
    }

    int tenkanSenPeriod = ((IntegerChromosome) chromosomes.get(0)).gene().allele();
    int kijunSenPeriod = ((IntegerChromosome) chromosomes.get(1)).gene().allele();
    int senkouSpanBPeriod = ((IntegerChromosome) chromosomes.get(2)).gene().allele();
    int chikouSpanPeriod = ((IntegerChromosome) chromosomes.get(3)).gene().allele();


    IchimokuCloudParameters parameters =
        IchimokuCloudParameters.newBuilder()
            .setTenkanSenPeriod(tenkanSenPeriod)
            .setKijunSenPeriod(kijunSenPeriod)
            .setSenkouSpanBPeriod(senkouSpanBPeriod)
            .setChikouSpanPeriod(chikouSpanPeriod)
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
    return StrategyType.ICHIMOKU_CLOUD;
  }
}
