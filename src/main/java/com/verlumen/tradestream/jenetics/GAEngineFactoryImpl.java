package com.verlumen.tradestream.backtesting;

import com.google.inject.Inject;
import com.verlumen.tradestream.backtesting.params.ChromosomeSpec;
import com.verlumen.tradestream.backtesting.params.ParamConfig;
import com.verlumen.tradestream.backtesting.params.ParamConfigManager;
import io.jenetics.DoubleChromosome;
import io.jenetics.DoubleGene;
import io.jenetics.Genotype;
import io.jenetics.Mutator;
import io.jenetics.SinglePointCrossover;
import io.jenetics.TournamentSelector;
import io.jenetics.engine.Engine;
import org.ta4j.core.BarSeries;

import java.util.List;
import java.util.stream.Collectors;

/**
 * Factory for creating genetic algorithm engines.
 * Encapsulates the engine configuration logic to make it reusable and testable.
 */
final class GAEngineFactoryImpl {
    private final ParamConfigManager paramConfigManager;
    private final FitnessCalculator fitnessCalculator;
    
    @Inject
    public GAEngineFactoryImpl(
            ParamConfigManager paramConfigManager,
            FitnessCalculator fitnessCalculator) {
        this.paramConfigManager = paramConfigManager;
        this.fitnessCalculator = fitnessCalculator;
    }
    
    /**
     * Creates a genetic algorithm engine configured for the given request.
     *
     * @param request the GA optimization request
     * @param series the bar series for backtesting
     * @param backtestRunner the backtest runner for fitness evaluation
     * @return a configured GA engine
     */
    @Override
    public Engine<DoubleGene, Double> createEngine(
            GAOptimizationRequest request,
            BarSeries series,
            BacktestRunner backtestRunner) {
        
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
            
        return Genotype.of(chromosomes);
    }
    
    private int getPopulationSize(GAOptimizationRequest request) {
        return request.getPopulationSize() > 0 
            ? request.getPopulationSize() 
            : GAConstants.DEFAULT_POPULATION_SIZE;
    }
}
