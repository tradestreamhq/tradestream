package com.verlumen.tradestream.discovery;

import com.google.protobuf.Any;
import io.jenetics.Genotype;
import java.io.Serializable;

/**
 * Converts genotypes from the genetic algorithm into strategy parameters. Encapsulates the
 * conversion logic to make it reusable and testable.
 */
public interface GenotypeConverter extends Serializable {
  /**
   * Converts the genotype from the genetic algorithm into strategy parameters.
   *
   * @param genotype the genotype resulting from the GA optimization
   * @param strategyName the name of the trading strategy being optimized (e.g., "MACD_CROSSOVER")
   * @return an Any instance containing the strategy parameters
   */
  Any convertToParameters(Genotype<?> genotype, String strategyName);
}
