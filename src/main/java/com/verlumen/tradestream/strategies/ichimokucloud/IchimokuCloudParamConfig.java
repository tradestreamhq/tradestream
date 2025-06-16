package com.verlumen.tradestream.strategies.ichimokucloud;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.IchimokuCloudParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.NumericChromosome;

public class IchimokuCloudParamConfig implements ParamConfig {

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    // Not implemented for this refactoring, returning empty list as placeholder
    return ImmutableList.of();
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    // Not implemented for this refactoring, using default parameters as placeholder
    return Any.pack(getDefaultParameters());
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    // Not implemented for this refactoring, returning empty list as placeholder
    return ImmutableList.of();
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.ICHIMOKU_CLOUD;
  }

  // Method as requested by the subtask
  public IchimokuCloudParameters getDefaultParameters() {
    return IchimokuCloudParameters.newBuilder()
        .setTenkanSenPeriod(9)
        .setKijunSenPeriod(26)
        .setSenkouSpanBPeriod(52)
        .setChikouSpanPeriod(26)
        .build();
  }
}
