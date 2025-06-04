package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.protobuf.Any
import com.verlumen.tradestream.discovery.DiscoveredStrategy
import com.verlumen.tradestream.discovery.StrategyDiscoveryRequest
import com.verlumen.tradestream.discovery.StrategyDiscoveryResult
import com.verlumen.tradestream.marketdata.InfluxDbCandleFetcher
import com.verlumen.tradestream.strategies.Strategy
import io.jenetics.Genotype
import io.jenetics.Phenotype
import io.jenetics.engine.Engine
import io.jenetics.engine.EvolutionResult
import io.jenetics.Gene
import org.apache.beam.sdk.transforms.DoFn

/**
 * Apache Beam transform that runs genetic algorithm optimization for trading strategy discovery.
 *
 * Input: StrategyDiscoveryRequest
 * Output: StrategyDiscoveryResult containing top performing strategies
 *
 * This transform:
 * 1. Fetches market data from InfluxDB
 * 2. Runs genetic algorithm optimization
 * 3. Converts best genotypes to strategy parameters
 * 4. Returns discovered strategies with performance scores
 *
 * All dependencies are injected via Guice.
 */
class RunGADiscoveryFn
    @Inject
    constructor(
        private val candleFetcher: InfluxDbCandleFetcher,
        private val gaEngineFactory: GAEngineFactory,
        private val genotypeConverter: GenotypeConverter,
    ) : DoFn<StrategyDiscoveryRequest, StrategyDiscoveryResult>() {
        companion object {
            private val logger = FluentLogger.forEnclosingClass()
        }

        @Setup
        fun setup() {
            logger.atInfo().log("RunGADiscoveryFn setup with injected dependencies.")
        }

        @ProcessElement
        fun processElement(context: ProcessContext) {
            val discoveryRequest = context.element()
            logger.atInfo().log(
                "Processing StrategyDiscoveryRequest for symbol: %s, type: %s",
                discoveryRequest.symbol,
                discoveryRequest.strategyType,
            )

            val candles =
                candleFetcher.fetchCandles(
                    discoveryRequest.symbol,
                    discoveryRequest.startTime,
                    discoveryRequest.endTime,
                )

            if (candles.isEmpty()) {
                logger.atWarning().log("No candles for request: %s. Skipping GA.", discoveryRequest.symbol)
                return
            }

            val engineParams = GAEngineParams(
                strategyType = discoveryRequest.strategyType,
                candlesList = candles,
                populationSize = discoveryRequest.gaConfig.populationSize
            )

            val engine: Engine<*, Double>
            try {
                engine = gaEngineFactory.createEngine(engineParams)
            } catch (e: Exception) {
                logger.atSevere().withCause(e).log("Error creating GA Engine for request: %s.", discoveryRequest.symbol)
                return
            }

            val evolutionResult
            try {
                evolutionResult = engine
                    .stream()
                    .limit(discoveryRequest.gaConfig.maxGenerations.toLong())
                    .collect(EvolutionResult.toBestEvolutionResult())
            } catch (e: Exception) {
                logger.atSevere().withCause(e).log("Error during GA evolution for %s", discoveryRequest.symbol)
                return
            }

            // Extract top N phenotypes from the final population
            val bestPhenotypes = evolutionResult
                .population()
                .sortedByDescending { it.fitness() }
                .take(discoveryRequest.topN)

            if (bestPhenotypes.isEmpty()) {
                logger.atWarning().log("GA run yielded no best phenotypes for %s", discoveryRequest.symbol)
                return
            }

            val resultBuilder = StrategyDiscoveryResult.newBuilder()
            for (phenotype in bestPhenotypes) {
                val bestGenotype = phenotype.genotype()
                val score = phenotype.fitness() as Double

                val strategyParamsAny: Any
                try {
                    strategyParamsAny = genotypeConverter.convertToParameters(bestGenotype as Genotype<*>, discoveryRequest.strategyType)
                } catch (e: Exception) {
                    logger.atWarning().withCause(e).log("Failed to convert genotype to parameters for %s", discoveryRequest.symbol)
                    continue // Skip this phenotype
                }

                val strategyProto =
                    Strategy
                        .newBuilder()
                        .setType(discoveryRequest.strategyType)
                        .setParameters(strategyParamsAny)
                        .build()

                val discoveredStrategy =
                    DiscoveredStrategy
                        .newBuilder()
                        .setStrategy(strategyProto)
                        .setScore(score)
                        .setSymbol(discoveryRequest.symbol)
                        .setStartTime(discoveryRequest.startTime)
                        .setEndTime(discoveryRequest.endTime)
                        .build()

                resultBuilder.addTopStrategies(discoveredStrategy)
            }

            val finalResult = resultBuilder.build()
            if (finalResult.topStrategiesCount > 0) {
                context.output(finalResult)
            } else {
                logger.atInfo().log("No strategies to output after GA processing for %s", discoveryRequest.symbol)
            }
        }

        @Teardown
        fun teardown() {
            candleFetcher.close()
            logger.atInfo().log("RunGADiscoveryFn teardown.")
        }
    }
