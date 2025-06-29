package com.verlumen.tradestream.strategies.doubletopbottom;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.DoubleTopBottomParameters;
import io.jenetics.NumericChromosome;

public final class DoubleTopBottomParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(ChromosomeSpec.ofInteger(10, 50));

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    if (chromosomes.size() != 1) {
      throw new IllegalArgumentException("Expected 1 chromosome, got " + chromosomes.size());
    }

    int period = ((NumericChromosome<Integer, ?>) chromosomes.get(0)).intValue();

    DoubleTopBottomParameters parameters =
        DoubleTopBottomParameters.newBuilder().setPeriod(period).build();

    return Any.pack(parameters);
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }
}
