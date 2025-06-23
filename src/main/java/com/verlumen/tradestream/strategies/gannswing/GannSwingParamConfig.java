package com.verlumen.tradestream.strategies.gannswing;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.GannSwingParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public final class GannSwingParamConfig implements ParamConfig {
  private static final int MIN_GANN_PERIOD = 2;
  private static final int MAX_GANN_PERIOD = 100;
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(ChromosomeSpec.ofInteger(MIN_GANN_PERIOD, MAX_GANN_PERIOD));

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    int gannPeriod = MIN_GANN_PERIOD;
    if (chromosomes != null && chromosomes.size() == 1) {
      gannPeriod = ((IntegerChromosome) chromosomes.get(0)).intValue();
    }
    return Any.pack(GannSwingParameters.newBuilder().setGannPeriod(gannPeriod).build());
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }
}
