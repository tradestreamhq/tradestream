package com.verlumen.tradestream.backtesting;

import com.google.inject.Inject;
import io.jenetics.Chromosome;
import io.jenetics.DoubleChromosome;
import io.jenetics.Genotype;
import io.jenetics.Mutator;
import io.jenetics.SinglePointCrossover;
import io.jenetics.TournamentSelector;
import io.jenetics.engine.Engine;
import io.jenetics.Gene;
import java.util.List;
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
    public Engine<Gene<?, ?>, Double> createEngine(GAOptimizationRequest request) {
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
       ParamConfig config = paramConfigManager.getParamConfig(request.getStrategyType());

       // Create chromosomes based on parameter specifications
       List<Chromosome<?>> chromosomes = config.getChromosomeSpecs().stream()
           .map(ChromosomeSpec::createChromosome)
           .collect(Collectors.toList());

       // Handle the case where no chromosomes are specified
       if (chromosomes.isEmpty()) {
           // Create a default chromosome for testing/fallback
           chromosomes.add(DoubleChromosome.of(0.0, 1.0));
       }

       return Genotype.of(chromosomes);
     }

    private int getPopulationSize(GAOptimizationRequest request) {
        return request.getPopulationSize() > 0
            ? request.getPopulationSize()
            : GAConstants.DEFAULT_POPULATION_SIZE;
    }
}
