package com.verlumen.tradestream.strategies.rangebars;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.RangeBarsParameters;
import io.jenetics.NumericChromosome;

public final class RangeBarsParamConfig implements ParamConfig {
  private static final double MIN_RANGE_SIZE = 0.1;
  private static final double MAX_RANGE_SIZE = 100.0;
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(ChromosomeSpec.ofDouble(MIN_RANGE_SIZE, MAX_RANGE_SIZE));

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    double rangeSize = MIN_RANGE_SIZE;
    if (!chromosomes.isEmpty()) {
      rangeSize = ((Number) chromosomes.get(0).gene().allele()).doubleValue();
    }
    RangeBarsParameters params = RangeBarsParameters.newBuilder().setRangeSize(rangeSize).build();
    return Any.pack(params);
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    ImmutableList.Builder<NumericChromosome<?, ?>> builder = ImmutableList.builder();
    for (ChromosomeSpec<?> spec : SPECS) {
      builder.add(spec.createChromosome());
    }
    return builder.build();
  }
}
