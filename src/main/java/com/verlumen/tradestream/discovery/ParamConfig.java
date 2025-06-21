package com.verlumen.tradestream.discovery;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import io.jenetics.NumericChromosome;
import java.io.Serializable;

/**
 * Represents configuration for a strategy's parameters that supports multiple parameter types.
 */
public interface ParamConfig extends Serializable {
  /**
   * Returns a list of chromosome specifications, each defining a parameter's type and constraints.
   */
  ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs();

  /**
   * Creates strategy parameters from a list of chromosomes.
   *
   * @param chromosomes The chromosomes containing optimized parameter values
   * @return Protocol buffer message containing the parameters
   */
  Any createParameters(ImmutableList<? extends NumericChromosome<?, ?>> chromosomes);

  /**
   * Creates initial chromosomes for this parameter configuration.
   *
   * @return List of initial chromosomes for optimization
   */
  ImmutableList<? extends NumericChromosome<?, ?>> initialChromosomes();
}
