package com.verlumen.tradestream.strategies.volumeprofile;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.VolumeProfileParameters;
import io.jenetics.NumericChromosome;

public final class VolumeProfileParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS = ImmutableList.of(
      ChromosomeSpec.ofInteger(10, 100));

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    try {
      int period = 20; // default value
      if (!chromosomes.isEmpty()) {
        period = ((Number) chromosomes.get(0).gene().allele()).intValue();
      }
      VolumeProfileParameters parameters = VolumeProfileParameters.newBuilder()
          .setPeriod(period)
          .build();
      return Any.pack(parameters);
    } catch (Exception e) {
      // Return default parameters if there's an error
      VolumeProfileParameters parameters = VolumeProfileParameters.newBuilder()
          .setPeriod(20)
          .build();
      return Any.pack(parameters);
    }
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }
} 