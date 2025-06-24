package com.verlumen.tradestream.strategies.aroonmfi;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.AroonMfiParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public class AroonMfiParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(10, 50), // Aroon Period
          ChromosomeSpec.ofInteger(10, 50), // MFI Period
          ChromosomeSpec.ofInteger(60, 90), // Overbought Threshold
          ChromosomeSpec.ofInteger(10, 40) // Oversold Threshold
          );

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    if (chromosomes.size() != SPECS.size()) {
      throw new IllegalArgumentException(
          "Expected " + SPECS.size() + " chromosomes but got " + chromosomes.size());
    }

    IntegerChromosome aroonPeriodChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome mfiPeriodChrom = (IntegerChromosome) chromosomes.get(1);
    IntegerChromosome overboughtChrom = (IntegerChromosome) chromosomes.get(2);
    IntegerChromosome oversoldChrom = (IntegerChromosome) chromosomes.get(3);

    AroonMfiParameters parameters =
        AroonMfiParameters.newBuilder()
            .setAroonPeriod(aroonPeriodChrom.gene().allele())
            .setMfiPeriod(mfiPeriodChrom.gene().allele())
            .setOverboughtThreshold(overboughtChrom.gene().allele())
            .setOversoldThreshold(oversoldChrom.gene().allele())
            .build();
    return Any.pack(parameters);
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }
}
