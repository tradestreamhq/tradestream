package com.verlumen.tradestream.backtesting.params;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import io.jenetics.Gene;
import io.jenetics.NumericChromosome;

/**
 * Represents configuration for a strategy's parameters that supports multiple parameter types.
 * Used by GeneticAlgorithmOrchestrator to optimize parameters.
 */
public interface ParamConfig {
    /**
     * Returns a list of chromosome specifications, each defining a parameter's type and constraints.
     */
    ImmutableList<ChromosomeSpec<?>> getChromosomeSpecs();

    /**
     * Creates strategy parameters from a list of chromosomes.
     * @param chromosomes The chromosomes containing optimized parameter values
     * @return Protocol buffer message containing the parameters 
     */
    Any createParameters(ImmutableList<? extends NumericChromosome<? extends Gene<?, ?>>> chromosomes);

    /**
     * Creates initial chromosomes for this parameter configuration.
     * @return List of initial chromosomes for optimization
     */
    ImmutableList<? extends NumericChromosome<? extends Gene<?, ?>>> initialChromosomes();
}
