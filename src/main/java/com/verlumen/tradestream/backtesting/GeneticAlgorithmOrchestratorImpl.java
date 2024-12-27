package com.verlumen.tradestream.backtesting;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import io.jenetics.*;
import io.jenetics.engine.*;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeries;
import java.time.ZonedDateTime;
import java.time.Duration;

/**
 * Implementation of GeneticAlgorithmOrchestrator using Jenetics library.
 * Evolves strategy parameters by evaluating fitness through backtesting.
 */
final class GeneticAlgorithmOrchestratorImpl implements GeneticAlgorithmOrchestrator {
    private static final int DEFAULT_POPULATION_SIZE = 50;
    private static final int DEFAULT_MAX_GENERATIONS = 100;
    private static final double MUTATION_PROBABILITY = 0.15;
    private static final double CROSSOVER_PROBABILITY = 0.35;

    private final BacktestService backtestService;

    @Inject
    GeneticAlgorithmOrchestratorImpl(BacktestService backtestService) {
        this.backtestService = backtestService;
    }

    @Override
    public BestStrategyResponse runOptimization(GAOptimizationRequest request) {
        checkArgument(!request.getCandlesList().isEmpty(), "Candles list cannot be empty");

        // Convert candles to BarSeries for evaluation
        BarSeries series = createBarSeries(request);

        // Configure genetic algorithm based on strategy type
        Engine<DoubleGene, Double> engine = configureEngine(request, series);

        // Run optimization
        Phenotype<DoubleGene, Double> best = engine.stream()
            .limit(request.getMaxGenerations() > 0 
                ? request.getMaxGenerations() 
                : DEFAULT_MAX_GENERATIONS)
            .collect(EvolutionResult.toBestPhenotype());

        // Convert best result to strategy parameters
        Any bestParams = convertToParameters(best.getGenotype(), request.getStrategyType());

        return BestStrategyResponse.newBuilder()
            .setBestStrategyParameters(bestParams)
            .setBestScore(best.getFitness())
            .build();
    }

    private Engine<DoubleGene, Double> configureEngine(
            GAOptimizationRequest request, BarSeries series) {
        // Configure chromosome based on strategy type
        ParamConfig config = getParamConfig(request.getStrategyType());

        // Create genotype factory for parameter ranges
        Factory<Genotype<DoubleGene>> gtf = Genotype.of(
            config.getChromosomes().stream()
                .map(range -> DoubleChromosome.of(
                    range.min(), range.max()))
                .collect(Collectors.toList())
        );

        // Create fitness function that evaluates parameters through backtesting
        Function<Genotype<DoubleGene>, Double> fitness = genotype -> {
            try {
                Any params = convertToParameters(genotype, request.getStrategyType());
                
                BacktestRequest backtestRequest = BacktestRequest.newBuilder()
                    .addAllCandles(request.getCandlesList())
                    .setStrategyType(request.getStrategyType())
                    .setStrategyParameters(params)
                    .build();

                BacktestResult result = backtestService.runBacktest(backtestRequest);
                return result.getOverallScore();
            } catch (Exception e) {
                return Double.NEGATIVE_INFINITY; // Penalize invalid parameter combinations
            }
        };

        return Engine.builder(fitness, gtf)
            .populationSize(request.getPopulationSize() > 0 
                ? request.getPopulationSize() 
                : DEFAULT_POPULATION_SIZE)
            .selector(new TournamentSelector<>(3))
            .alterers(
                new Mutator<>(MUTATION_PROBABILITY),
                new SinglePointCrossover<>(CROSSOVER_PROBABILITY))
            .build();
    }

    private BarSeries createBarSeries(GAOptimizationRequest request) {
        BaseBarSeries series = new BaseBarSeries();
        ZonedDateTime now = ZonedDateTime.now();
        
        request.getCandlesList().forEach(candle -> 
            series.addBar(Duration.ofMinutes(1), 
                now.plusMinutes(series.getBarCount()),
                candle.getOpen(),
                candle.getHigh(),
                candle.getLow(),
                candle.getClose(),
                candle.getVolume())
        );
        
        return series;
    }

    private Any convertToParameters(Genotype<DoubleGene> genotype, StrategyType type) {
        ParamConfig config = getParamConfig(type);
        return config.createParameters(genotype);
    }

    private ParamConfig getParamConfig(StrategyType type) {
        switch (type) {
            case SMA_RSI:
                return new SmaRsiParamConfig();
            // Add other strategy types here
            default:
                throw new IllegalArgumentException("Unsupported strategy type: " + type);
        }
    }
}
