package com.verlumen.tradestream.backtesting.momentumoscillators;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.backtesting.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.AdxStochasticParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;

final class AdxStochasticParamConfig implements ParamConfig {
  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          // Integer parameters
          ChromosomeSpec.ofInteger(10, 30), // ADX Period
          ChromosomeSpec.ofInteger(5, 20), // Stochastic K Period
          ChromosomeSpec.ofInteger(3, 15), // Stochastic D Period (smoothing)
          ChromosomeSpec.ofInteger(60, 90), // Overbought Threshold
          ChromosomeSpec.ofInteger(10, 40) // Oversold Threshold
          );

  static AdxStochasticParamConfig create() {
    return new AdxStochasticParamConfig();
  }

  private AdxStochasticParamConfig() {}

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

    // Extract parameters with proper casting
    IntegerChromosome adxPeriodChrom = (IntegerChromosome) chromosomes.get(0);
    IntegerChromosome stochasticKChrom = (IntegerChromosome) chromosomes.get(1);
    IntegerChromosome stochasticDChrom = (IntegerChromosome) chromosomes.get(2);
    IntegerChromosome overboughtChrom = (IntegerChromosome) chromosomes.get(3);
    IntegerChromosome oversoldChrom = (IntegerChromosome) chromosomes.get(4);

    // Build parameters
    AdxStochasticParameters parameters =
        AdxStochasticParameters.newBuilder()
            .setAdxPeriod(adxPeriodChrom.gene().allele())
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
    return StrategyType.ADX_STOCHASTIC;
  }
}
