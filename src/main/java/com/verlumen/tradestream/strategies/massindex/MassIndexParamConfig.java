package com.verlumen.tradestream.strategies.massindex;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.MassIndexParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.logging.Logger;

/**
 * Configuration for Mass Index strategy parameters.
 *
 * <p>The Mass Index is designed to identify trend reversals based on changes in the High-Low range.
 * It uses the High-Low range, EMA of the High-Low range, Double EMA of the High-Low range, and sums
 * the ratio of the EMA to the Double EMA.
 */
public final class MassIndexParamConfig implements ParamConfig {

  private static final Logger logger = Logger.getLogger(MassIndexParamConfig.class.getName());

  private static final ImmutableList<ChromosomeSpec<?>> SPECS =
      ImmutableList.of(
          ChromosomeSpec.ofInteger(5, 50), // EMA Period
          ChromosomeSpec.ofInteger(5, 25) // Sum Period
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
                + " - Using default values for Mass Index parameters");

        return Any.pack(MassIndexParameters.newBuilder().setEmaPeriod(9).setSumPeriod(25).build());
      }

      int emaPeriod = getIntegerValue(chromosomes, 0, 9);
      int sumPeriod = getIntegerValue(chromosomes, 1, 25);

      MassIndexParameters parameters =
          MassIndexParameters.newBuilder().setEmaPeriod(emaPeriod).setSumPeriod(sumPeriod).build();

      return Any.pack(parameters);
    } catch (Exception e) {
      logger.warning(
          "Error creating Mass Index parameters: " + e.getMessage() + " - Using default values");

      return Any.pack(MassIndexParameters.newBuilder().setEmaPeriod(9).setSumPeriod(25).build());
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
