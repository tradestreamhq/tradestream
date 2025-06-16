package com.verlumen.tradestream.strategies.aroonmfi;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.AroonMfiParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.NumericChromosome;

public class AroonMfiParamConfig implements ParamConfig {

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    // Not implemented for this refactoring, returning empty list as placeholder
    return ImmutableList.of();
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    // Not implemented for this refactoring, using default parameters as placeholder
    // In a real scenario, this would map chromosomes to AroonMfiParameters
    return Any.pack(getDefaultParameters());
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    // Not implemented for this refactoring, returning empty list as placeholder
    return ImmutableList.of();
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.AROON_MFI;
  }

  // Method as requested by the subtask
  public AroonMfiParameters getDefaultParameters() {
    return AroonMfiParameters.newBuilder()
        .setAroonPeriod(25)
        .setMfiPeriod(14)
        .setOverboughtThreshold(80)
        .setOversoldThreshold(20)
        .build();
  }
}
