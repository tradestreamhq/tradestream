package com.verlumen.tradestream.backtesting;

import com.google.inject.Inject;
import io.jenetics.Chromosome;
import io.jenetics.DoubleChromosome;
import io.jenetics.Genotype;
import io.jenetics.IntegerChromosome;
import io.jenetics.Mutator;
import io.jenetics.NumericChromosome;
import io.jenetics.SinglePointCrossover;
import io.jenetics.TournamentSelector;
import io.jenetics.engine.Engine;
import java.util.ArrayList;
import java.util.List;
import java.util.logging.Logger;

final class GAEngineFactoryImpl implements GAEngineFactory {
  private static final Logger logger = Logger.getLogger(GAEngineFactoryImpl.class.getName());

  private final ParamConfigManager paramConfigManager;
  private final FitnessCalculator fitnessCalculator;

  @Inject
  GAEngineFactoryImpl(ParamConfigManager paramConfigManager, FitnessCalculator fitnessCalculator) {
    this.paramConfigManager = paramConfigManager;
    this.fitnessCalculator = fitnessCalculator;
  }

  @Override
  public Engine<?, Double> createEngine(GAOptimizationRequest request) {
    // Create the initial genotype from the parameter specifications
    Genotype<?> gtf = createGenotype(request);

    // Build and return the GA engine with the specified settings
    return Engine.builder(fitnessCalculator.createFitnessFunction(request), gtf)
        .populationSize(getPopulationSize(request))
        .selector(new TournamentSelector<>(GAConstants.TOURNAMENT_SIZE))
        .alterers(
            new Mutator<>(GAConstants.MUTATION_PROBABILITY),
            new SinglePointCrossover<>(GAConstants.CROSSOVER_PROBABILITY))
        .build();
  }

  /**
   * Creates a genotype based on parameter specifications.
   *
   * @param request the GA optimization request
   * @return a genotype with chromosomes configured according to parameter specifications
   */
  private Genotype<?> createGenotype(GAOptimizationRequest request) {
    try {
      ParamConfig config = paramConfigManager.getParamConfig(request.getStrategyType());

      // Get the chromosomes from the parameter configuration
      List<? extends NumericChromosome<?, ?>> numericChromosomes = config.initialChromosomes();

      if (numericChromosomes.isEmpty()) {
        logger.warning("No chromosomes defined for strategy type: " + request.getStrategyType());
        return Genotype.of(DoubleChromosome.of(0.0, 1.0));
      }

      // For simplicity and to avoid generic type issues, we'll use the first chromosome as a
      // template
      // and recreate all chromosomes to have the same type
      Chromosome<?> firstChromosome = numericChromosomes.get(0);

      if (firstChromosome instanceof DoubleChromosome) {
        // Handle case where we need DoubleChromosome type
        List<DoubleChromosome> doubleChromosomes = new ArrayList<>();
        for (NumericChromosome<?, ?> chr : numericChromosomes) {
          if (chr instanceof DoubleChromosome) {
            doubleChromosomes.add((DoubleChromosome) chr);
          } else {
            // Convert to DoubleChromosome
            double value = chr.gene().doubleValue();
            doubleChromosomes.add(DoubleChromosome.of(value, value * 2));
          }
        }
        return Genotype.of(doubleChromosomes);
      } else if (firstChromosome instanceof IntegerChromosome) {
        // Handle case where we need IntegerChromosome type
        List<IntegerChromosome> integerChromosomes = new ArrayList<>();
        for (NumericChromosome<?, ?> chr : numericChromosomes) {
          if (chr instanceof IntegerChromosome) {
            integerChromosomes.add((IntegerChromosome) chr);
          } else {
            // Convert to IntegerChromosome
            int value = (int) chr.gene().doubleValue();
            integerChromosomes.add(IntegerChromosome.of(value, value * 2));
          }
        }
        return Genotype.of(integerChromosomes);
      } else {
        // Default to DoubleChromosome if the type is unknown
        logger.warning(
            "Unsupported chromosome type: "
                + firstChromosome.getClass().getName()
                + ". Using default DoubleChromosome.");
        return Genotype.of(DoubleChromosome.of(0.0, 1.0));
      }
    } catch (Exception e) {
      logger.warning(
          "Error creating genotype for strategy type "
              + request.getStrategyType()
              + ": "
              + e.getMessage());
      // Fallback to a simple genotype with a single chromosome
      return Genotype.of(DoubleChromosome.of(0.0, 1.0));
    }
  }

  private int getPopulationSize(GAOptimizationRequest request) {
    return request.getPopulationSize() > 0
        ? request.getPopulationSize()
        : GAConstants.DEFAULT_POPULATION_SIZE;
  }
}
