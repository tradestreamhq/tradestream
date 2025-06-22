package com.verlumen.tradestream.strategies.momentumpinball;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.MomentumPinballParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

/**
 * Parameter configuration for the Momentum Pinball strategy.
 *
 * <p>This strategy combines short term and long term momentum indicators to identify trading
 * opportunities. It enters when long momentum is positive and short momentum crosses above a
 * threshold, and exits when long momentum is negative and short momentum crosses below a threshold.
 */
public class MomentumPinballParamConfig implements ParamConfig {

  private static final Logger logger = Logger.getLogger(MomentumPinballParamConfig.class.getName());

  private static final int DEFAULT_SHORT_PERIOD = 10;
  private static final int DEFAULT_LONG_PERIOD = 20;

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(2, 30), // shortPeriod
          ChromosomeSpec.ofInteger(5, 60)  // longPeriod
      );

  public StrategyType getStrategyType() {
    return StrategyType.MOMENTUM_PINBALL;
  }

  public Any getDefaultParameters() {
    return Any.pack(
        MomentumPinballParameters.newBuilder()
            .setShortPeriod(DEFAULT_SHORT_PERIOD)
            .setLongPeriod(DEFAULT_LONG_PERIOD)
            .build());
  }

  public MomentumPinballParameters unpack(Any parameters)
      throws InvalidProtocolBufferException {
    return parameters.unpack(MomentumPinballParameters.class);
  }

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    try {
      if (chromosomes.size() != SPECS.size()) {
        logger.warning(
            "Expected " + SPECS.size() + " chromosomes but got " + chromosomes.size() + " - Using default values for Momentum Pinball parameters");
        return getDefaultParameters();
      }
      int shortPeriod = getIntegerValue(chromosomes, 0, DEFAULT_SHORT_PERIOD);
      int longPeriod = getIntegerValue(chromosomes, 1, DEFAULT_LONG_PERIOD);
      MomentumPinballParameters parameters =
          MomentumPinballParameters.newBuilder()
              .setShortPeriod(shortPeriod)
              .setLongPeriod(longPeriod)
              .build();
      return Any.pack(parameters);
    } catch (Exception e) {
      logger.warning("Error creating Momentum Pinball parameters: " + e.getMessage() + " - Using default values");
      return getDefaultParameters();
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