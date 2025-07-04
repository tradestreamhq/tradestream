package com.verlumen.tradestream.discovery;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.verlumen.tradestream.strategies.StrategySpec;
import com.verlumen.tradestream.strategies.StrategySpecsKt;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.Chromosome;
import io.jenetics.Genotype;
import io.jenetics.NumericChromosome;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/**
 * Converts genotypes from the genetic algorithm into strategy parameters. Encapsulates the
 * conversion logic to make it reusable and testable.
 */
final class GenotypeConverterImpl implements GenotypeConverter {
  @Inject
  GenotypeConverterImpl() {}

  /**
   * Converts the genotype from the genetic algorithm into strategy parameters.
   *
   * @param genotype the genotype resulting from the GA optimization
   * @param type the type of trading strategy being optimized
   * @return an Any instance containing the strategy parameters
   * @throws NullPointerException if genotype or type is null
   * @throws IllegalArgumentException if the chromosome types are invalid
   */
  @Override
  public Any convertToParameters(Genotype<?> genotype, StrategyType type) {
    // Ensure genotype and type are not null
    Objects.requireNonNull(genotype, "Genotype cannot be null");
    Objects.requireNonNull(type, "Strategy type cannot be null");

    // Get the parameter configuration for the strategy
    StrategySpec spec = StrategySpecsKt.getSpec(type);
    ParamConfig config = spec.getParamConfig();

    // Extract chromosomes from the genotype
    List<NumericChromosome<?, ?>> chromosomes = new ArrayList<>();
    for (Chromosome<?> chromosome : genotype) {
      if (chromosome instanceof NumericChromosome) {
        chromosomes.add((NumericChromosome<?, ?>) chromosome);
      } else {
        throw new IllegalArgumentException(
            "Unsupported chromosome type: " + chromosome.getClass().getName());
      }
    }

    // Create parameters from the chromosomes
    return config.createParameters(ImmutableList.copyOf(chromosomes));
  }
}
