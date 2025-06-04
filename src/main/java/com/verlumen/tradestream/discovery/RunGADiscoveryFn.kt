package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.protobuf.Any
import com.verlumen.tradestream.discovery.DiscoveredStrategy
import com.verlumen.tradestream.discovery.StrategyDiscoveryRequest
import com.verlumen.tradestream.discovery.StrategyDiscoveryResult
import com.verlumen.tradestream.marketdata.InfluxDbCandleFetcher
import com.verlumen.tradestream.strategies.Strategy
import io.jenetics.DoubleGene
import io.jenetics.Genotype
import io.jenetics.engine.Engine
import io.jenetics.engine.EvolutionResult
import org.apache.beam.sdk.transforms.DoFn

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

            val engineParams =
                GAEngineParams(
                    strategyType = discoveryRequest.strategyType,
                    candlesList = candles,
                    populationSize = discoveryRequest.gaConfig.populationSize,
                )

            val engine: Engine<DoubleGene, Double>
            try {
                @Suppress("UNCHECKED_CAST")
                engine = gaEngineFactory.createEngine(engineParams) as Engine<DoubleGene, Double>
            } catch (e: Exception) {
                logger.atSevere().withCause(e).log("Error creating GA Engine for request: %s.", discoveryRequest.symbol)
                return
            }

            val evolutionResult: EvolutionResult<DoubleGene, Double>
            try {
                evolutionResult =
                    engine
                        .stream()
                        .limit(discoveryRequest.gaConfig.maxGenerations.toLong())
                        .collect(EvolutionResult.toBestEvolutionResult())
            } catch (e: Exception) {
                logger.atSevere().withCause(e).log("Error during GA evolution for %s", discoveryRequest.symbol)
                return
            }

            val bestPhenotypes =
                evolutionResult
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
                val score = phenotype.fitness()

                val strategyParamsAny: Any
                try {
                    strategyParamsAny =
                        genotypeConverter.convertToParameters(
                            bestGenotype as Genotype<DoubleGene>,
                            discoveryRequest.strategyType,
                        )
                } catch (e: Exception) {
                    logger.atWarning().withCause(e).log("Failed to convert genotype to parameters for %s", discoveryRequest.symbol)
                    continue
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

            val discoveryResult = resultBuilder.build()
            if (discoveryResult.topStrategiesCount > 0) {
                context.output(discoveryResult)
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
