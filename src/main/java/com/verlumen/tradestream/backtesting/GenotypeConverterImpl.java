package com.verlumen.tradestream.backtesting;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.verlumen.tradestream.backtesting.params.NumericChromosome;
import com.verlumen.tradestream.backtesting.params.ParamConfig;
import com.verlumen.tradestream.backtesting.params.ParamConfigManager;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.DoubleGene;
import io.jenetics.Genotype;

/**
 * Converts genotypes from the genetic algorithm into strategy parameters.
 * Encapsulates the conversion logic to make it reusable and testable.
 */
public class GenotypeConverterImpl implements GenotypeConverter {
  private final ParamConfigManager paramConfigManager;

  @Inject
  public GenotypeConverterImpl(ParamConfigManager paramConfigManager) {
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
  public Any convertToParameters(Genotype<DoubleGene> genotype, StrategyType type) {
    ParamConfig config = paramConfigManager.getParamConfig(type);

    // Convert Jenetics chromosomes to numeric chromosomes
    ImmutableList<NumericChromosome<?, ?>> numericChromosomes =
        genotype.stream()
            .map(chromosome -> (NumericChromosome<?, ?>) chromosome)
            .collect(ImmutableList.toImmutableList());

    return config.createParameters(numericChromosomes);
  }
}
