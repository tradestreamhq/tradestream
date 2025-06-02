package com.verlumen.tradestream.discovery

import com.google.protobuf.Any
import com.google.protobuf.InvalidProtocolBufferException
import com.google.protobuf.util.JsonFormat // For serializing Any to JSON
import com.verlumen.tradestream.backtesting.GAEngineFactory // Java
import com.verlumen.tradestream.backtesting.GAOptimizationRequest // Java Proto
import com.verlumen.tradestream.backtesting.GenotypeConverter // Java
// import com.verlumen.tradestream.backtesting.FitnessCalculator // Java (or BacktestRunner)
// Import your specific GA implementation classes as needed
// e.g., import com.verlumen.tradestream.backtesting.somepackage.*
import com.verlumen.tradestream.marketdata.InfluxDbCandleFetcher // New Kotlin class
import com.verlumen.tradestream.discovery.proto.Discovery.DiscoveredStrategy // Proto
import com.verlumen.tradestream.discovery.proto.Discovery.StrategyDiscoveryRequest // Proto
import com.verlumen.tradestream.discovery.proto.Discovery.StrategyDiscoveryResult // Proto
import com.verlumen.tradestream.strategies.Strategy // Proto
// Example param proto import (ensure you have this or similar)
// import com.verlumen.tradestream.strategies.SmaRsiParameters
import io.jenetics.Genotype
import io.jenetics.Phenotype
import io.jenetics.engine.Engine
import io.jenetics.engine.EvolutionResult
// import io.jenetics.DoubleGene // Or your Gene type
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.io.jdbc.JdbcIO
import org.apache.beam.sdk.io.kafka.KafkaIO
import org.apache.beam.sdk.options.PipelineOptionsFactory
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.KV
import org.apache.kafka.common.serialization.ByteArrayDeserializer
import org.apache.kafka.common.serialization.StringDeserializer
import com.google.common.flogger.FluentLogger
import java.sql.PreparedStatement
import java.sql.SQLException
import java.security.MessageDigest // For SHA256 hashing

// Main pipeline object or class
object StrategyDiscoveryPipeline {
    private val logger = FluentLogger.forEnclosingClass()

    @JvmStatic // Needed if main is in an object
    fun main(args: Array<String>) {
        val options =
            PipelineOptionsFactory
                .fromArgs(*args)
                .withValidation()
                .`as`(StrategyDiscoveryPipelineOptions::class.java)
        options.isStreaming = true // Assuming this is a streaming pipeline as per Kafka source

        val pipeline = Pipeline.create(options)

        pipeline
            .apply(
                "ReadDiscoveryRequestsFromKafka",
                KafkaIO
                    .read<String, ByteArray>()
                    .withBootstrapServers(options.kafkaBootstrapServers)
                    .withTopic(options.strategyDiscoveryRequestTopic)
                    .withKeyDeserializer(StringDeserializer::class.java)
                    .withValueDeserializer(ByteArrayDeserializer::class.java),
            ).apply("DeserializeProtoRequests", ParDo.of(DeserializeStrategyDiscoveryRequestFn()))
            .apply("RunGAStrategyDiscovery", ParDo.of(RunGADiscoveryFn(options))) // Pass options here
            .apply("ExtractDiscoveredStrategies", ParDo.of(ExtractDiscoveredStrategiesFn()))
            .apply(
                "WriteStrategiesToDatabase",
                JdbcIO
                    .write<DiscoveredStrategy>()
                    .withDataSourceConfiguration(
                        JdbcIO.DataSourceConfiguration
                            .create(
                                "org.postgresql.Driver",
                                options.databaseJdbcUrl ?: throw IllegalArgumentException("Database JDBC URL is required"),
                            ).withUsername(options.databaseUsername ?: throw IllegalArgumentException("Database username is required"))
                            .withPassword(options.databasePassword ?: throw IllegalArgumentException("Database password is required")),
                    ).withStatement(
                        """
                        INSERT INTO Strategies (strategy_id, symbol, strategy_type, parameters, first_discovered_at, last_evaluated_at, current_score, is_active, strategy_hash, discovery_symbol, discovery_start_time, discovery_end_time)
                        VALUES (gen_random_uuid(), ?, ?, ?::jsonb, NOW(), NOW(), ?, TRUE, ?, ?, ?, ?)
                        ON CONFLICT (strategy_hash) DO UPDATE SET current_score = EXCLUDED.current_score, last_evaluated_at = NOW()
                        """.trimIndent(),
                    ).withPreparedStatementSetter(DiscoveredStrategyToStrategiesStatementSetter()),
            )
        pipeline.run().waitUntilFinish()
    }
}

class DeserializeStrategyDiscoveryRequestFn : DoFn<KV<String, ByteArray>, StrategyDiscoveryRequest>() {
    private val logger = FluentLogger.forEnclosingClass()

    @ProcessElement
    fun processElement(context: ProcessContext) {
        val kafkaValue = context.element().value
        if (kafkaValue != null) {
            try {
                val request = StrategyDiscoveryRequest.parseFrom(kafkaValue)
                context.output(request)
            } catch (e: InvalidProtocolBufferException) {
                logger.atSevere().withCause(e).log("Failed to deserialize StrategyDiscoveryRequest proto.")
            }
        }
    }
}

class RunGADiscoveryFn(
    private val options: StrategyDiscoveryPipelineOptions,
) : DoFn<StrategyDiscoveryRequest, StrategyDiscoveryResult>() {
    private val logger = FluentLogger.forEnclosingClass()

    @Transient private var candleFetcher: InfluxDbCandleFetcher? = null

    // AI NOTE: GAEngineFactory and GenotypeConverter instantiation needs to be addressed.
    // Your existing Java components (e.g., GAEngineFactoryImpl, GenotypeConverterImpl) likely
    // rely on a DI framework like Guice. In a Beam DoFn, direct Guice injection isn't straightforward.
    // Options include:
    // 1. Manual Instantiation: Create instances manually in @Setup, passing dependencies. This might be complex.
    // 2. Beam-compatible DI: Use a Beam-friendly DI approach if available in your project.
    // 3. Service Locator Pattern: Pass a factory/locator to the DoFn to get instances.
    // For this example, placeholders for manual instantiation are included but will require adaptation.
    @Transient private var gaEngineFactory: GAEngineFactory? = null

    @Transient private var genotypeConverter: GenotypeConverter? = null

    @Setup
    fun setup() {
        candleFetcher =
            InfluxDbCandleFetcher(
                options.influxDbUrl,
                options.influxDbToken ?: throw IllegalArgumentException("InfluxDB token is required."),
                options.influxDbOrg,
                options.influxDbBucket,
            )
        logger.atInfo().log("RunGADiscoveryFn setup with Influx Candle Fetcher.")

        // TODO AI: Instantiate gaEngineFactory and genotypeConverter here.
        // This requires adapting your existing Java Guice-based DI from com.verlumen.tradestream.backtesting
        // to manual instantiation or a Beam-compatible DI approach.
        // Example (conceptual, actual dependencies and constructors will vary):
        // val paramConfigManager = ParamConfigManagerImpl(ParamConfigs.ALL_CONFIGS) // Assuming this is accessible
        // genotypeConverter = GenotypeConverterImpl(paramConfigManager)
        // val fitnessCalculator = FitnessCalculatorImpl(
        // BacktestRequestFactoryImpl(), // May need to instantiate or pass
        // BacktestRunnerImpl(BarSeriesFactoryImpl(), StrategyManagerImpl(StrategyFactories.ALL_FACTORIES)), // May need to instantiate or pass
        // genotypeConverter!!
        // )
        // gaEngineFactory = GAEngineFactoryImpl(paramConfigManager, fitnessCalculator)

        if (gaEngineFactory == null || genotypeConverter == null) {
            logger.atWarning().log(
                "GA components (GAEngineFactory, GenotypeConverter) were NOT initialized in RunGADiscoveryFn setup. GA execution will be SKIPPED.",
            )
        } else {
            logger.atInfo().log("GA components (GAEngineFactory, GenotypeConverter) initialized successfully.")
        }
    }

    @ProcessElement
    fun processElement(context: ProcessContext) {
        val discoveryRequest = context.element()
        logger.atInfo().log(
            "Processing StrategyDiscoveryRequest for symbol: %s, type: %s",
            discoveryRequest.symbol,
            discoveryRequest.strategyType,
        )

        val currentCandleFetcher =
            candleFetcher ?: run {
                logger.atSevere().log("InfluxDbCandleFetcher not initialized in RunGADiscoveryFn. Skipping request.")
                return
            }
        val currentGaEngineFactory =
            gaEngineFactory ?: run {
                logger.atSevere().log("GAEngineFactory not initialized. Cannot run GA for request. Skipping.")
                return
            }
        val currentGenotypeConverter =
            genotypeConverter ?: run {
                logger.atSevere().log("GenotypeConverter not initialized. Cannot convert GA results for request. Skipping.")
                return
            }

        val candles =
            currentCandleFetcher.fetchCandles(
                discoveryRequest.symbol,
                discoveryRequest.startTime,
                discoveryRequest.endTime,
            )

        if (candles.isEmpty) {
            logger.atWarning().log("No candles for request: %s. Skipping GA.", discoveryRequest.symbol)
            return
        }

        val gaOptimizationRequest =
            GAOptimizationRequest
                .newBuilder()
                .addAllCandles(candles)
                .setStrategyType(discoveryRequest.strategyType)
                .setMaxGenerations(discoveryRequest.gaConfig.maxGenerations)
                .setPopulationSize(discoveryRequest.gaConfig.populationSize)
                .build()

        val engine: Engine<*, Double>
        try {
            // The cast might be necessary depending on how GAEngineFactory is defined.
            // If it returns Engine<?, ?> or similar raw type, a cast is needed.
            // If it's already generic like Engine<G, C extends Comparable<? super C>>, ensure types match.
            @Suppress("UNCHECKED_CAST")
            engine = currentGaEngineFactory.createEngine(gaOptimizationRequest) as Engine<io.jenetics.Gene<*, *>, Double>
        } catch (e: ClassCastException) {
            logger
                .atSevere()
                .withCause(
                    e,
                ).log("Failed to cast GA Engine for request: %s. Check type compatibility.", discoveryRequest.symbol)
            return
        } catch (e: Exception) {
            logger.atSevere().withCause(e).log("Error creating GA Engine for request: %s.", discoveryRequest.symbol)
            return
        }

        val bestPhenotypes: List<Phenotype<io.jenetics.Gene<*, *>, Double>>
        try {
            bestPhenotypes =
                engine
                    .stream()
                    // It's common for GA libraries to use long for limits.
                    // Ensure discoveryRequest.topN is converted appropriately if it's Int.
                    .limit(discoveryRequest.topN.toLong())
                    .collect(EvolutionResult.toBestPhenotypes())
        } catch (e: Exception) {
            logger.atSevere().withCause(e).log("Error during GA evolution for %s", discoveryRequest.symbol)
            return
        }

        if (bestPhenotypes.isEmpty()) {
            logger.atWarning().log("GA run yielded no best phenotypes for %s", discoveryRequest.symbol)
            return
        }

        val resultBuilder = StrategyDiscoveryResult.newBuilder()
        for (phenotype in bestPhenotypes) {
            // Ensure the genotype from phenotype is cast correctly.
            // The exact type of Gene (e.g., DoubleGene, IntegerGene) depends on your GA setup.
            @Suppress("UNCHECKED_CAST")
            val bestGenotype = phenotype.genotype() as Genotype<io.jenetics.Gene<*, *>>
            val score = phenotype.fitness()

            val strategyParamsAny: Any
            try {
                strategyParamsAny = currentGenotypeConverter.convertToParameters(bestGenotype, discoveryRequest.strategyType)
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
        candleFetcher?.close()
        logger.atInfo().log("RunGADiscoveryFn teardown.")
    }
}

class ExtractDiscoveredStrategiesFn : DoFn<StrategyDiscoveryResult, DiscoveredStrategy>() {
    @ProcessElement
    fun processElement(context: ProcessContext) {
        val result = context.element()
        result?.topStrategiesList?.forEach { context.output(it) }
    }
}

class DiscoveredStrategyToStrategiesStatementSetter : JdbcIO.PreparedStatementSetter<DiscoveredStrategy> {
    private val logger = FluentLogger.forEnclosingClass()

    // Helper function to generate SHA256 hash
    private fun sha256(input: String): String {
        val bytes = input.toByteArray()
        val md = MessageDigest.getInstance("SHA-256")
        val digest = md.digest(bytes)
        return digest.fold("") { str, it -> str + "%02x".format(it) }
    }

    override fun setParameters(
        element: DiscoveredStrategy,
        preparedStatement: PreparedStatement,
    ) {
        try {
            preparedStatement.setString(1, element.symbol)
            preparedStatement.setString(2, element.strategy.type.name)

            val paramsJson =
                try {
                    JsonFormat.printer().print(element.strategy.parameters)
                } catch (e: InvalidProtocolBufferException) {
                    logger
                        .atWarning()
                        .withCause(
                            e,
                        ).log(
                            "Could not format strategy parameters to JSON for strategy type: %s. Parameters: %s",
                            element.strategy.type,
                            element.strategy.parameters,
                        )
                    "{}" // Default to empty JSON object
                }
            preparedStatement.setString(3, paramsJson)
            preparedStatement.setDouble(4, element.score)

            // More robust hash: include symbol, type, and serialized parameters for uniqueness
            val hashInput = "${element.symbol}:${element.strategy.type.name}:$paramsJson"
            val strategyHash = sha256(hashInput)
            preparedStatement.setString(5, strategyHash)

            preparedStatement.setString(6, element.symbol) // discovery_symbol
            preparedStatement.setTimestamp(
                7,
                java.sql.Timestamp.from(Instant.ofEpochSecond(element.startTime.seconds, element.startTime.nanos.toLong())),
            )
            preparedStatement.setTimestamp(
                8,
                java.sql.Timestamp.from(Instant.ofEpochSecond(element.endTime.seconds, element.endTime.nanos.toLong())),
            )
        } catch (e: SQLException) {
            logger
                .atSevere()
                .withCause(
                    e,
                ).log(
                    "SQL Exception while setting parameters for DiscoveredStrategy for symbol %s. Strategy: %s",
                    element.symbol,
                    element.strategy.type,
                )
            throw e // Re-throw to allow Beam to handle it
        } catch (e: Exception) {
            logger
                .atSevere()
                .withCause(
                    e,
                ).log(
                    "Unexpected exception while setting parameters for DiscoveredStrategy for symbol %s. Strategy: %s",
                    element.symbol,
                    element.strategy.type,
                )
            throw SQLException("Wrapped unexpected exception", e) // Wrap in SQLException for Beam to handle
        }
    }
}
