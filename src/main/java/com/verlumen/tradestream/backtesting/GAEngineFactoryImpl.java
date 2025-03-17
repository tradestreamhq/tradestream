package com.verlumen.tradestream.backtesting;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;
import io.jenetics.Chromosome;
import io.jenetics.DoubleChromosome;
import io.jenetics.Gene;
import io.jenetics.Genotype;
import io.jenetics.IntegerChromosome;
import io.jenetics.Mutator;
import io.jenetics.NumericChromosome;
import io.jenetics.NumericGene;
import io.jenetics.SinglePointCrossover;
import io.jenetics.TournamentSelector;
import io.jenetics.engine.Engine;
import java.util.List;
import java.util.ArrayList;
import java.util.logging.Logger;
import java.util.stream.Collectors;

final class GAEngineFactoryImpl implements GAEngineFactory {
    private static final Logger logger = Logger.getLogger(GAEngineFactoryImpl.class.getName());

    private final ParamConfigManager paramConfigManager;
    private final FitnessCalculator fitnessCalculator;

    @Inject
    GAEngineFactoryImpl(
        ParamConfigManager paramConfigManager,
        FitnessCalculator fitnessCalculator) {
        this.paramConfigManager = paramConfigManager;
        this.fitnessCalculator = fitnessCalculator;
    }

    @Override
    public Engine<?, Double> createEngine(GAOptimizationRequest request) {
        // Create the initial genotype from the parameter specifications
        Genotype<?> gtf = createGenotype(request);

        // Build and return the GA engine with the specified settings
        return Engine
            .builder(fitnessCalculator.createFitnessFunction(request), gtf)
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

           // Always use the exact chromosomes from the config's initialChromosomes method
           // This ensures we have the correct number and types of chromosomes
           List<? extends NumericChromosome<?, ?>> numericChromosomes = config.initialChromosomes();
           
           if (numericChromosomes.isEmpty()) {
               logger.warning("No chromosomes defined for strategy type: " + request.getStrategyType());
               return Genotype.of(DoubleChromosome.of(0.0, 1.0));
           }
           
           // Instead of trying to categorize and convert, just use the chromosomes directly
           // The initialChromosomes() method should return properly formatted chromosomes
           List<Chromosome<?>> chromosomes = new ArrayList<>();
           for (NumericChromosome<?, ?> chr : numericChromosomes) {
               chromosomes.add(chr);
           }
           
           // Create genotype from the chromosomes
           return Genotype.of(chromosomes);
           
       } catch (Exception e) {
           logger.warning("Error creating genotype for strategy type " + 
               request.getStrategyType() + ": " + e.getMessage());
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
