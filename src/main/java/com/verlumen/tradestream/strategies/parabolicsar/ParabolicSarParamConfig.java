package com.verlumen.tradestream.strategies.parabolicsar;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.ParabolicSarParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.NumericChromosome;

public class ParabolicSarParamConfig implements ParamConfig {

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
    return StrategyType.PARABOLIC_SAR;
  }

  // Method as requested by the subtask
  public ParabolicSarParameters getDefaultParameters() {
    return ParabolicSarParameters.newBuilder()
        .setAccelerationFactorStart(0.02)
        .setAccelerationFactorIncrement(0.02)
        .setAccelerationFactorMax(0.2)
        .build();
  }
}
