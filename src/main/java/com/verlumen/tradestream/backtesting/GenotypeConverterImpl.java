package com.verlumen.tradestream.backtesting;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.Chromosome;
import io.jenetics.DoubleChromosome;
import io.jenetics.DoubleGene;
import io.jenetics.Gene;
import io.jenetics.Genotype;
import io.jenetics.IntegerChromosome;
import io.jenetics.LongChromosome;
import io.jenetics.NumericChromosome;
import java.io.Serializable;

/**
 * Converts genotypes from the genetic algorithm into strategy parameters. Encapsulates the
 * conversion logic to make it reusable and testable.
 */
final class GenotypeConverterImpl implements GenotypeConverter {

  private final ParamConfigManager paramConfigManager;

  @Inject
  GenotypeConverterImpl(ParamConfigManager paramConfigManager) {
    this.paramConfigManager = paramConfigManager;
  }

  /**
   * Converts the genotype from the genetic algorithm into strategy parameters.
   *
   * @param genotype the genotype resulting from the GA optimization
   * @param type the type of trading strategy being optimized
   * @return an Any instance containing the strategy parameters
   */
  @Override
  public Any convertToParameters(Genotype<?> genotype, StrategyType type) { // Corrected generic type
    return convertToParametersHelper(genotype, type);
  }

  /**
   * Helper function for convertToParameters to handle different chromosome types. It uses the correct
   * generic type for Genotype and works for all the numeric types.
   */
  private Any convertToParametersHelper(Genotype<?> genotype, StrategyType type) {
    ParamConfig config = paramConfigManager.getParamConfig(type);

    ImmutableList.Builder<NumericChromosome<?, ?>> builder = ImmutableList.builder();
    for (Chromosome<?> chromosome : genotype) {
      // Now we can check the instance type of the chromosome
      if (chromosome instanceof IntegerChromosome) {
        builder.add((IntegerChromosome) chromosome);
      } else if (chromosome instanceof LongChromosome) {
        builder.add((LongChromosome) chromosome);
      } else if (chromosome instanceof DoubleChromosome) {
        builder.add((DoubleChromosome) chromosome);
      }
    }

    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = builder.build();
    return config.createParameters(chromosomes);
  }
}
