package com.verlumen.tradestream.backtesting;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.verlumen.tradestream.backtesting.params.ChromosomeSpec;
import com.verlumen.tradestream.backtesting.params.ParamConfig;
import com.verlumen.tradestream.backtesting.params.ParamConfigManager;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.ta4j.BarSeriesBuilder;
import io.jenetics.*;
import io.jenetics.engine.*;
import java.util.List;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.ta4j.core.BarSeries;

/**
 * Implementation of the GeneticAlgorithmOrchestrator interface.
 * This class configures and runs a genetic algorithm to optimize trading strategies
 * based on backtesting results.
 */
final class GeneticAlgorithmOrchestratorImpl implements GeneticAlgorithmOrchestrator {
    private static final int DEFAULT_POPULATION_SIZE = 50;
    private static final int DEFAULT_MAX_GENERATIONS = 100;
    private static final double MUTATION_PROBABILITY = 0.15;
    private static final double CROSSOVER_PROBABILITY = 0.35;

    private final BacktestServiceClient backtestServiceClient;
    private final ParamConfigManager paramConfigManager;

    /**
     * Constructs a new GeneticAlgorithmOrchestratorImpl.
     *
     * @param backtestServiceClient the client used to run backtests
     * @param paramConfigManager the manager for parameter configurations
     */
    @Inject
    GeneticAlgorithmOrchestratorImpl(
        BacktestServiceClient backtestServiceClient, ParamConfigManager paramConfigManager) {
        this.backtestServiceClient = backtestServiceClient;
        this.paramConfigManager = paramConfigManager;
    }

    /**
     * Runs the genetic algorithm optimization for a given trading strategy.
     *
     * @param request the GA optimization request containing the strategy type, candles, and other settings
     * @return a response containing the best strategy parameters and corresponding fitness score
     * @throws IllegalArgumentException if the request's candles list is empty
     */
    @Override
    public BestStrategyResponse runOptimization(GAOptimizationRequest request) {
        checkArgument(!request.getCandlesList().isEmpty(), "Candles list cannot be empty");

        // Create a bar series from the provided candles
        BarSeries series = createBarSeries(request);
        
        // Configure the genetic algorithm engine with the strategy and backtest service
        Engine<DoubleGene, Double> engine = configureEngine(request, series);

        // Execute the GA and collect the best phenotype from the evolution process
        Phenotype<DoubleGene, Double> best = engine.stream()
            .limit(request.getMaxGenerations() > 0 
                ? request.getMaxGenerations() 
                : DEFAULT_MAX_GENERATIONS)
            .collect(EvolutionResult.toBestPhenotype());

        // Convert the best genotype into strategy parameters
        Any bestParams = convertToParameters(best.genotype(), request.getStrategyType());

        return BestStrategyResponse.newBuilder()
            .setBestStrategyParameters(bestParams)
            .setBestScore(best.fitness())
            .build();
    }

    /**
     * Configures the genetic algorithm engine.
     *
     * <p>This method creates the initial genotype from the chromosome specifications,
     * defines the fitness function based on the backtest results, and sets up the GA
     * parameters such as population size, mutation and crossover probabilities.
     *
     * @param request the optimization request containing strategy type and other parameters
     * @param series the bar series constructed from the provided candles
     * @return the configured GA engine
     */
    private Engine<DoubleGene, Double> configureEngine(
            GAOptimizationRequest request, BarSeries series) {
        ParamConfig config = paramConfigManager.getParamConfig(request.getStrategyType());

        // Create chromosomes based on parameter specifications from the configuration
        List<DoubleChromosome> chromosomes = config.getChromosomeSpecs().stream()
            .map(spec -> {
                ChromosomeSpec<?> paramSpec = spec;
                double min = ((Number) paramSpec.getRange().lowerEndpoint()).doubleValue();
                double max = ((Number) paramSpec.getRange().upperEndpoint()).doubleValue();
                return DoubleChromosome.of(min, max);
            })
            .collect(Collectors.toList());

        // Build the initial genotype from the chromosomes
        Genotype<DoubleGene> gtf = Genotype.of(chromosomes);

        // Define the fitness function using backtesting to evaluate the performance of a strategy
        Function<Genotype<DoubleGene>, Double> fitness = genotype -> {
            try {
                Any params = convertToParameters(genotype, request.getStrategyType());
                
                BacktestRequest backtestRequest = BacktestRequest.newBuilder()
                    .addAllCandles(request.getCandlesList())
                    .setStrategyType(request.getStrategyType())
                    .setStrategyParameters(params)
                    .build();

                BacktestResult result = backtestServiceClient.runBacktest(backtestRequest);
                return result.getOverallScore();
            } catch (Exception e) {
                // Penalize any invalid genotype by assigning the lowest possible fitness
                return Double.NEGATIVE_INFINITY;
            }
        };

        // Build and return the GA engine with the specified settings
        return Engine
            .builder(fitness, gtf)
            .populationSize(request.getPopulationSize() > 0 
                ? request.getPopulationSize() 
                : DEFAULT_POPULATION_SIZE)
            .selector(new TournamentSelector<>(3))
            .alterers(
                new Mutator<>(MUTATION_PROBABILITY),
                new SinglePointCrossover<>(CROSSOVER_PROBABILITY))
            .build();
    }

    /**
     * Creates a bar series from the provided GA optimization request.
     *
     * @param request the optimization request containing candle data
     * @return a BarSeries constructed from the candle data
     */
    private BarSeries createBarSeries(GAOptimizationRequest request) {
        return BarSeriesBuilder.createBarSeries(
            ImmutableList.copyOf(request.getCandlesList())
        );
    }

    /**
     * Converts the genotype from the genetic algorithm into strategy parameters.
     *
     * @param genotype the genotype resulting from the GA optimization
     * @param type the type of trading strategy being optimized
     * @return an Any instance containing the strategy parameters
     */
    private Any convertToParameters(Genotype<DoubleGene> genotype, StrategyType type) {
        ParamConfig config = paramConfigManager.getParamConfig(type);
        
        // Convert Jenetics chromosomes to numeric chromosomes
        ImmutableList<NumericChromosome<?, ?>> numericChromosomes = genotype.stream()
            .map(chromosome -> (NumericChromosome<?, ?>) chromosome)
            .collect(ImmutableList.toImmutableList());
            
        return config.createParameters(numericChromosomes);
    }
}
