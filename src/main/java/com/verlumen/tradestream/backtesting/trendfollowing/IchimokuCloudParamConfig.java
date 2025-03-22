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
  // Individual chromosome specs
  private static final ChromosomeSpec<?> TENKAN_SEN_PERIOD_SPEC = 
      ChromosomeSpec.ofInteger(5, 60);

  private static final ChromosomeSpec<?> KIJUN_SEN_PERIOD_SPEC = 
      ChromosomeSpec.ofInteger(10, 120);

  private static final ChromosomeSpec<?> SENKOU_SPAN_B_PERIOD_SPEC = 
      ChromosomeSpec.ofInteger(20, 240);

  private static final ChromosomeSpec<?> CHIKOU_SPAN_PERIOD_SPEC = 
      ChromosomeSpec.ofInteger(10, 120);

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          TENKAN_SEN_PERIOD_SPEC,
          KIJUN_SEN_PERIOD_SPEC,
          SENKOU_SPAN_B_PERIOD_SPEC,
          CHIKOU_SPAN_PERIOD_SPEC
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

    // Directly get the first value from each chromosome
    IntegerChromosome tenkanSenChromosome = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome kijunSenChromosome = (IntegerChromosome) chromosomes.get(1);
    IntegerChromosome senkouSpanBChromosome = (IntegerChromosome) chromosomes.get(2);
    IntegerChromosome chikouSpanChromosome = (IntegerChromosome) chromosomes.get(3);
    
    // Use the get(0) method to access the first gene
    int tenkanSenPeriod = tenkanSenChromosome.get(0).allele();
    int kijunSenPeriod = kijunSenChromosome.get(0).allele();
    int senkouSpanBPeriod = senkouSpanBChromosome.get(0).allele();
    int chikouSpanPeriod = chikouSpanChromosome.get(0).allele();

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
