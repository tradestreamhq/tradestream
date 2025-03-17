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
import java.util.stream.Collectors;

final class GAEngineFactoryImpl implements GAEngineFactory {
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

           // Get the chromosomes from the parameter configuration
           List<? extends NumericChromosome<?, ?>> numericChromosomes = config.initialChromosomes();
           
           // If no chromosomes are specified, create a default one
           if (numericChromosomes.isEmpty()) {
               return Genotype.of(DoubleChromosome.of(0.0, 1.0));
           }
           
           // Check the type of the first chromosome to determine the genotype type
           Chromosome<?> firstChromosome = numericChromosomes.get(0);
           
           if (firstChromosome instanceof DoubleChromosome) {
               // Handle DoubleChromosome type
               List<DoubleChromosome> doubleChromosomes = new ArrayList<>();
               for (NumericChromosome<?, ?> chr : numericChromosomes) {
                   if (chr instanceof DoubleChromosome) {
                       doubleChromosomes.add((DoubleChromosome) chr);
                   } else {
                       throw new IllegalArgumentException("Mixed chromosome types are not supported. Found " + 
                           chr.getClass().getName() + " while expecting DoubleChromosome");
                   }
               }
               return Genotype.of(doubleChromosomes);
           } else if (firstChromosome instanceof IntegerChromosome) {
               // Handle IntegerChromosome type
               List<IntegerChromosome> integerChromosomes = new ArrayList<>();
               for (NumericChromosome<?, ?> chr : numericChromosomes) {
                   if (chr instanceof IntegerChromosome) {
                       integerChromosomes.add((IntegerChromosome) chr);
                   } else {
                       throw new IllegalArgumentException("Mixed chromosome types are not supported. Found " + 
                           chr.getClass().getName() + " while expecting IntegerChromosome");
                   }
               }
               return Genotype.of(integerChromosomes);
           } else {
               throw new IllegalArgumentException("Unsupported chromosome type: " + 
                   firstChromosome.getClass().getName());
           }
       } catch (IllegalArgumentException e) {
           // For missing parameter configurations, create a default genotype
           // This is a fallback to prevent the application from crashing
           return Genotype.of(DoubleChromosome.of(0.0, 1.0));
       }
     }

    private int getPopulationSize(GAOptimizationRequest request) {
        return request.getPopulationSize() > 0
            ? request.getPopulationSize()
            : GAConstants.DEFAULT_POPULATION_SIZE;
    }
}
