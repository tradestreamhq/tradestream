package com.verlumen.tradestream.discovery;

import com.google.protobuf.Any;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.NumericChromosome;
import java.io.Serializable;
import java.util.List

/**
 * Represents configuration for a strategy's parameters that supports multiple parameter types.
 */
public interface ParamConfig extends Serializable {
  /**
   * Returns a list of chromosome specifications, each defining a parameter's type and constraints.
   */
  List<ChromosomeSpec<?>> getChromosomeSpecs();

  /**
   * Creates strategy parameters from a list of chromosomes.
   *
   * @param chromosomes The chromosomes containing optimized parameter values
   * @return Protocol buffer message containing the parameters
   */
  Any createParameters(List<? extends NumericChromosome<?, ?>> chromosomes);

  /**
   * Creates initial chromosomes for this parameter configuration.
   *
   * @return List of initial chromosomes for optimization
   */
  List<? extends NumericChromosome<?, ?>> initialChromosomes();

  /**
   * Returns the strategy type that this parameter configuration is for.
   *
   * @return The strategy type associated with these parameters
   */
  StrategyType getStrategyType();
}
