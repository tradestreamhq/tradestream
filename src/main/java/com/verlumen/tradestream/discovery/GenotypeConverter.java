package com.verlumen.tradestream.discovery;

import com.google.protobuf.Any;
import com.verlumen.tradestream.strategies.StrategyType;
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
   * @param type the type of trading strategy being optimized
   * @return an Any instance containing the strategy parameters
   */
  Any convertToParameters(Genotype<?> genotype, StrategyType type);
}
