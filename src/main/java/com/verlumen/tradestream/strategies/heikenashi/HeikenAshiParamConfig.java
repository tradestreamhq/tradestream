package com.verlumen.tradestream.strategies.heikenashi;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.HeikenAshiParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public final class HeikenAshiParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(2, 30) // period
          );

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return ImmutableList.of(IntegerChromosome.of(2, 30, 14));
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    int period = ((IntegerChromosome) chromosomes.get(0)).intValue();
    return Any.pack(HeikenAshiParameters.newBuilder().setPeriod(period).build());
  }
}
