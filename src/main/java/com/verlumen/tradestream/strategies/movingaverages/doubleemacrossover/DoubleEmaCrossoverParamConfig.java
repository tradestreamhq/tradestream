package com.verlumen.tradestream.strategies.movingaverages.doubleemacrossover;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig; // Corrected interface
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.NumericChromosome;

public class DoubleEmaCrossoverParamConfig implements ParamConfig {

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
    return StrategyType.DOUBLE_EMA_CROSSOVER;
  }

  // Method as requested by the subtask
  public DoubleEmaCrossoverParameters getDefaultParameters() {
    return DoubleEmaCrossoverParameters.newBuilder()
        .setShortEmaPeriod(10) // As per subtask example
        .setLongEmaPeriod(20)  // As per subtask example
        .build();
  }
}
