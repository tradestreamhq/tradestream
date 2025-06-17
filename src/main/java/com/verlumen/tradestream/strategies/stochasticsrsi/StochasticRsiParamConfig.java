package com.verlumen.tradestream.strategies.stochasticsrsi;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.StochasticRsiParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

public final class StochasticRsiParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 30),  // RSI Period
          ChromosomeSpec.ofInteger(5, 30),  // Stochastic K Period
          ChromosomeSpec.ofInteger(3, 15),  // Stochastic D Period
          ChromosomeSpec.ofInteger(60, 95), // Overbought Threshold
          ChromosomeSpec.ofInteger(5, 40)   // Oversold Threshold
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

    IntegerChromosome rsiPeriodChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome stochasticKChrom = (IntegerChromosome) chromosomes.get(1);
    IntegerChromosome stochasticDChrom = (IntegerChromosome) chromosomes.get(2);
    IntegerChromosome overboughtChrom = (IntegerChromosome) chromosomes.get(3);
    IntegerChromosome oversoldChrom = (IntegerChromosome) chromosomes.get(4);

    StochasticRsiParameters parameters =
        StochasticRsiParameters.newBuilder()
            .setRsiPeriod(rsiPeriodChrom.gene().allele())
            .setStochasticKPeriod(stochasticKChrom.gene().allele())
            .setStochasticDPeriod(stochasticDChrom.gene().allele())
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

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.STOCHASTIC_RSI;
  }
}
