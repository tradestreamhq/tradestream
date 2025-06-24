package com.verlumen.tradestream.strategies.stochasticema;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.StochasticEmaParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

/**
 * Configuration for Stochastic EMA strategy parameters.
 *
 * <p>The Stochastic EMA combines the Stochastic Oscillator with an Exponential Moving Average to
 * identify overbought/oversold conditions and trend direction.
 */
public final class StochasticEmaParamConfig implements ParamConfig {

  private static final Logger logger = Logger.getLogger(StochasticEmaParamConfig.class.getName());

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 50), // EMA Period
          ChromosomeSpec.ofInteger(5, 50), // Stochastic K Period
          ChromosomeSpec.ofInteger(5, 50), // Stochastic D Period
          ChromosomeSpec.ofInteger(70, 90), // Overbought Threshold
          ChromosomeSpec.ofInteger(10, 30) // Oversold Threshold
          );

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    try {
      if (chromosomes.size() != SPECS.size()) {
        logger.warning(
            "Expected "
                + SPECS.size()
                + " chromosomes but got "
                + chromosomes.size()
                + " - Using default values for Stochastic EMA parameters");

        return Any.pack(
            StochasticEmaParameters.newBuilder()
                .setEmaPeriod(14)
                .setStochasticKPeriod(14)
                .setStochasticDPeriod(3)
                .setOverboughtThreshold(80)
                .setOversoldThreshold(20)
                .build());
      }

      int emaPeriod = getIntegerValue(chromosomes, 0, 14);
      int stochasticKPeriod = getIntegerValue(chromosomes, 1, 14);
      int stochasticDPeriod = getIntegerValue(chromosomes, 2, 3);
      int overboughtThreshold = getIntegerValue(chromosomes, 3, 80);
      int oversoldThreshold = getIntegerValue(chromosomes, 4, 20);

      StochasticEmaParameters parameters =
          StochasticEmaParameters.newBuilder()
              .setEmaPeriod(emaPeriod)
              .setStochasticKPeriod(stochasticKPeriod)
              .setStochasticDPeriod(stochasticDPeriod)
              .setOverboughtThreshold(overboughtThreshold)
              .setOversoldThreshold(oversoldThreshold)
              .build();

      return Any.pack(parameters);
    } catch (Exception e) {
      logger.warning(
          "Error creating Stochastic EMA parameters: "
              + e.getMessage()
              + " - Using default values");

      return Any.pack(
          StochasticEmaParameters.newBuilder()
              .setEmaPeriod(14)
              .setStochasticKPeriod(14)
              .setStochasticDPeriod(3)
              .setOverboughtThreshold(80)
              .setOversoldThreshold(20)
              .build());
    }
  }

  private int getIntegerValue(
      ImmutableList<? extends NumericChromosome<?, ?>> chromosomes, int index, int defaultValue) {
    try {
      if (index >= chromosomes.size()) {
        return defaultValue;
      }

      NumericChromosome<?, ?> chromosome = chromosomes.get(index);
      if (chromosome instanceof IntegerChromosome) {
        return ((IntegerChromosome) chromosome).gene().intValue();
      } else {
        return (int) chromosome.gene().doubleValue();
      }
    } catch (Exception e) {
      return defaultValue;
    }
  }

  @Override
  public ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes() {
    return SPECS.stream()
        .map(ChromosomeSpec::createChromosome)
        .collect(ImmutableList.toImmutableList());
  }
}
