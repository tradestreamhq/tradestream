package com.verlumen.tradestream.strategies.movingaverages.smaemacrossover;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.SmaEmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.NumericChromosome;

public class SmaEmaCrossoverParamConfig implements ParamConfig {

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
    return StrategyType.SMA_EMA_CROSSOVER;
  }

  // Method as requested by the subtask
  public SmaEmaCrossoverParameters getDefaultParameters() {
    return SmaEmaCrossoverParameters.newBuilder()
        .setSmaPeriod(50) // As per subtask example
        .setEmaPeriod(20)  // As per subtask example
        .build();
  }
}
