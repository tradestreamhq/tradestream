package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.google.protobuf.Any
import com.verlumen.tradestream.discovery.DiscoveredStrategy
import com.verlumen.tradestream.discovery.StrategyDiscoveryRequest
import com.verlumen.tradestream.discovery.StrategyDiscoveryResult
import com.verlumen.tradestream.marketdata.CandleFetcher
import com.verlumen.tradestream.strategies.Strategy
import io.jenetics.engine.Engine
import io.jenetics.engine.EvolutionResult
import org.apache.beam.sdk.transforms.DoFn
import java.io.Serializable
import java.util.Comparator

class RunGADiscoveryFn :
    DoFn<StrategyDiscoveryRequest, StrategyDiscoveryResult>,
    Serializable {
    private val candleFetcher: CandleFetcher
    private val gaEngineFactory: GAEngineFactory
    private val genotypeConverter: GenotypeConverter

    @Inject
    constructor(
        @Assisted candleFetcher: CandleFetcher,
        gaEngineFactory: GAEngineFactory,
        genotypeConverter: GenotypeConverter,
    ) {
        this.candleFetcher = candleFetcher
        this.gaEngineFactory = gaEngineFactory
        this.genotypeConverter = genotypeConverter
    }

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val serialVersionUID = 1L // Added serialVersionUID
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

        // 1) Fetch candles
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

        // 2) Build GAEngineParams
        val engineParams =
            GAEngineParams(
                strategyType = discoveryRequest.strategyType,
                candlesList = candles,
                populationSize = discoveryRequest.gaConfig.populationSize,
            )

        // 3) Create the Engine locally (never stored in a field)
        val engine: Engine<*, Double> = // Changed to Engine<*, Double> for broader compatibility
            try {
                gaEngineFactory.createEngine(engineParams)
            } catch (e: Exception) {
                logger.atSevere().withCause(e).log("Error creating GA Engine for request: %s.", discoveryRequest.symbol)
                return
            }

        // 4) Run the evolution (also local)
        val evolutionResult: EvolutionResult<*, Double>
        try {
            val stream =
                engine
                    .stream()
                    .limit(discoveryRequest.gaConfig.maxGenerations.toLong())
            // Fixed: Use Comparator.comparing with bestFitness() instead of naturalOrder
            val optionalResult = stream.max(Comparator.comparing<EvolutionResult<*, Double>, Double> { it.bestFitness() })

            if (!optionalResult.isPresent) {
                logger.atWarning().log(
                    "GA evolution stream was empty for %s after limit %d. Max generations: %d",
                    discoveryRequest.symbol,
                    discoveryRequest.gaConfig.maxGenerations.toLong(),
                    discoveryRequest.gaConfig.maxGenerations,
                )
                return
            }
            evolutionResult = optionalResult.get()
        } catch (e: Exception) {
            logger.atSevere().withCause(e).log("Error during GA evolution for %s", discoveryRequest.symbol)
            return
        }

        // 5) Pick top N phenotypes
        val bestPhenotypes =
            evolutionResult
                .population()
                .sortedByDescending { it.fitness() }
                .take(discoveryRequest.topN)

        if (bestPhenotypes.isEmpty()) {
            logger.atWarning().log("GA run yielded no best phenotypes for %s", discoveryRequest.symbol)
            return
        }

        // 6) Build the StrategyDiscoveryResult
        val resultBuilder = StrategyDiscoveryResult.newBuilder()
        for (phenotype in bestPhenotypes) {
            val bestGenotype = phenotype.genotype()
            val score = phenotype.fitness()

            val strategyParamsAny: Any =
                try {
                    genotypeConverter.convertToParameters(
                        bestGenotype, // Pass Genotype<*>
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
}
