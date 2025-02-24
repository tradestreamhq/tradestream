package com.verlumen.tradestream.backtesting;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.verlumen.tradestream.backtesting.params.ChromosomeSpec;
import com.verlumen.tradestream.backtesting.params.ParamConfig;
import com.verlumen.tradestream.backtesting.params.ParamConfigManager;
import com.verlumen.tradestream.strategies.Strategy;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.*;
import io.jenetics.engine.*;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeries;
import java.time.ZonedDateTime;
import java.time.Duration;

final class GeneticAlgorithmOrchestratorImpl implements GeneticAlgorithmOrchestrator {
    private static final int DEFAULT_POPULATION_SIZE = 50;
    private static final int DEFAULT_MAX_GENERATIONS = 100;
    private static final double MUTATION_PROBABILITY = 0.15;
    private static final double CROSSOVER_PROBABILITY = 0.35;

    private final BacktestServiceClient backtestServiceClient;
    private final ParamConfigManager paramConfigManager;

    @Inject
    GeneticAlgorithmOrchestratorImpl(
        BacktestServiceClient backtestServiceClient, ParamConfigManager paramConfigManager) {
        this.backtestServiceClient = backtestServiceClient;
        this.paramConfigManager = paramConfigManager;
    }

    @Override
    public BestStrategyResponse runOptimization(GAOptimizationRequest request) {
        checkArgument(!request.getCandlesList().isEmpty(), "Candles list cannot be empty");

        BarSeries series = createBarSeries(request);
        Engine<DoubleGene, Double> engine = configureEngine(request, series);

        Phenotype<DoubleGene, Double> best = engine.stream()
            .limit(request.getMaxGenerations() > 0 
                ? request.getMaxGenerations() 
                : DEFAULT_MAX_GENERATIONS)
            .collect(EvolutionResult.toBestPhenotype());

        Any bestParams = convertToParameters(best.genotype(), request.getStrategy().getType());

        return BestStrategyResponse.newBuilder()
            .setBestStrategyParameters(bestParams)
            .setBestScore(best.fitness())
            .build();
    }

    private Engine<DoubleGene, Double> configureEngine(
            GAOptimizationRequest request, BarSeries series) {
        ParamConfig config = paramConfigManager.getParamConfig(request.getStrategy().getType());

        // Create chromosomes based on parameter specs
        List<DoubleChromosome> chromosomes = config.getChromosomeSpecs().stream()
            .map(spec -> {
                ChromosomeSpec<?> paramSpec = spec;
                double min = ((Number) paramSpec.getRange().lowerEndpoint()).doubleValue();
                double max = ((Number) paramSpec.getRange().upperEndpoint()).doubleValue();
                return DoubleChromosome.of(min, max);
            })
            .collect(Collectors.toList());

        Genotype<DoubleGene> gtf = Genotype.of(chromosomes);

        Function<Genotype<DoubleGene>, Double> fitness = genotype -> {
            try {
                Any params = convertToParameters(genotype, request.getStrategy().getType());
                
                BacktestRequest backtestRequest = BacktestRequest.newBuilder()
                    .addAllCandles(request.getCandlesList())
                    .setStrategy(Strategy.newBuilder().setType(request.getStrategy().getType()).setParameters(params))
                    .build();

                BacktestResult result = backtestServiceClient.runBacktest(backtestRequest);
                return result.getOverallScore();
            } catch (Exception e) {
                return Double.NEGATIVE_INFINITY;
            }
        };

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
        ParamConfig config = paramConfigManager.getParamConfig(type);
        
        // Convert Jenetics chromosomes to numeric chromosomes
        ImmutableList<NumericChromosome<?, ?>> numericChromosomes = genotype.stream()
            .map(chromosome -> (NumericChromosome<?, ?>) chromosome)
            .collect(ImmutableList.toImmutableList());
            
        return config.createParameters(numericChromosomes);
    }
}
