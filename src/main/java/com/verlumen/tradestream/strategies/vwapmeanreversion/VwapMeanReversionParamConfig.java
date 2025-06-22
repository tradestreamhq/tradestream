package com.verlumen.tradestream.strategies.vwapmeanreversion;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.VwapMeanReversionParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

public final class VwapMeanReversionParamConfig implements ParamConfig {
  private static final Logger logger =
      Logger.getLogger(VwapMeanReversionParamConfig.class.getName());

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(10, 50), // vwapPeriod
          ChromosomeSpec.ofInteger(10, 50), // movingAveragePeriod
          ChromosomeSpec.ofDouble(1.0, 3.0) // deviationMultiplier
          );

  @Override
  public ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs() {
    return SPECS;
  }

  @Override
  public Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes) {
    try {
      if (chromosomes.size() != SPECS.size()) {
        logger.warning("Expected " + SPECS.size() + " chromosomes but got " + chromosomes.size());
        return getDefaultParameters();
      }

      int vwapPeriod = getIntegerValue(chromosomes, 0, 20);
      int movingAveragePeriod = getIntegerValue(chromosomes, 1, 20);
      double deviationMultiplier = getDoubleValue(chromosomes, 2, 2.0);

      return Any.pack(
          VwapMeanReversionParameters.newBuilder()
              .setVwapPeriod(vwapPeriod)
              .setMovingAveragePeriod(movingAveragePeriod)
              .setDeviationMultiplier(deviationMultiplier)
              .build());
    } catch (Exception e) {
      logger.warning("Error creating parameters: " + e.getMessage());
      return getDefaultParameters();
    }
  }

  private Any getDefaultParameters() {
    return Any.pack(
        VwapMeanReversionParameters.newBuilder()
            .setVwapPeriod(20)
            .setMovingAveragePeriod(20)
            .setDeviationMultiplier(2.0)
            .build());
  }

  private int getIntegerValue(
      ImmutableList<? extends NumericChromosome<?, ?>> chromosomes, int index, int defaultValue) {
    try {
      if (index >= chromosomes.size()) return defaultValue;
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

  private double getDoubleValue(
      ImmutableList<? extends NumericChromosome<?, ?>> chromosomes,
      int index,
      double defaultValue) {
    try {
      if (index >= chromosomes.size()) return defaultValue;
      NumericChromosome<?, ?> chromosome = chromosomes.get(index);
      if (chromosome instanceof DoubleChromosome) {
        return ((DoubleChromosome) chromosome).gene().doubleValue();
      } else {
        return chromosome.gene().doubleValue();
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
