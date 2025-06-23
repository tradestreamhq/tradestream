package com.verlumen.tradestream.strategies.renkochart;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.RenkoChartParameters;
import io.jenetics.NumericChromosome;

public final class RenkoChartParamConfig implements ParamConfig {
  private static final double MIN_BRICK_SIZE = 0.1;
  private static final double MAX_BRICK_SIZE = 100.0;
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(ChromosomeSpec.ofDouble(MIN_BRICK_SIZE, MAX_BRICK_SIZE));

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    double brickSize = MIN_BRICK_SIZE;
    if (!chromosomes.isEmpty()) {
      brickSize = ((Number) chromosomes.get(0).gene().allele()).doubleValue();
    }
    RenkoChartParameters params = RenkoChartParameters.newBuilder().setBrickSize(brickSize).build();
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
