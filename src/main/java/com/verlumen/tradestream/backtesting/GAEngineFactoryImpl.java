package com.verlumen.tradestream.backtesting;

import com.google.inject.Inject;
import io.jenetics.DoubleChromosome;
import io.jenetics.DoubleGene;
import io.jenetics.Genotype;
import io.jenetics.Mutator;
import io.jenetics.SinglePointCrossover;
import io.jenetics.TournamentSelector;
import io.jenetics.engine.Engine;
import io.jenetics.util.RandomRegistry;
import org.apache.commons.rng.simple.JDKRandomBridge;
import org.apache.commons.rng.simple.RandomSource;
import java.util.List;
import java.util.stream.Collectors;

final class GAEngineFactoryImpl implements GAEngineFactory {
    static {
        try {
            RandomRegistry.random(
                new JDKRandomBridge(
                    RandomSource.XOR_SHIFT_1024_S,
                    System.nanoTime()
                )
            );
        } catch (Exception e) {
            System.err.println("Error during static RNG initialization: " + e.getMessage());
            e.printStackTrace();
            // Optionally, rethrow as a runtime exception
            throw new ExceptionInInitializerError(e);
        }
    }

    private final ParamConfigManager paramConfigManager;
    private final FitnessCalculator fitnessCalculator;
    
    @Inject
    public GAEngineFactoryImpl(
            ParamConfigManager paramConfigManager,
            FitnessCalculator fitnessCalculator) {
        this.paramConfigManager = paramConfigManager;
        this.fitnessCalculator = fitnessCalculator;
    }
    
    @Override
    public Engine<DoubleGene, Double> createEngine(GAOptimizationRequest request) {
        // Create the initial genotype from the parameter specifications
        Genotype<DoubleGene> gtf = createGenotype(request);
        
        // Build and return the GA engine with the specified settings
        return Engine
            .builder(fitnessCalculator.createFitnessFunction(request), gtf)
            .populationSize(getPopulationSize(request))
            .selector(new TournamentSelector<>(3))
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
    private Genotype<DoubleGene> createGenotype(GAOptimizationRequest request) {
        ParamConfig config = paramConfigManager.getParamConfig(request.getStrategyType());
        
        // Create chromosomes based on parameter specifications
        List<DoubleChromosome> chromosomes = config.getChromosomeSpecs().stream()
            .map(spec -> {
                ChromosomeSpec<?> paramSpec = spec;
                double min = ((Number) paramSpec.getRange().lowerEndpoint()).doubleValue();
                double max = ((Number) paramSpec.getRange().upperEndpoint()).doubleValue();
                return DoubleChromosome.of(min, max);
            })
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
