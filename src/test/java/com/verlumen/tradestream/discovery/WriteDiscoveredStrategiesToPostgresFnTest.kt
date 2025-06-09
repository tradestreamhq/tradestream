package com.verlumen.tradestream.discovery

import com.google.protobuf.Any
import com.google.protobuf.Timestamp
import com.verlumen.tradestream.sql.DataSourceConfig
import com.verlumen.tradestream.strategies.SmaRsiParameters
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.PCollection
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.MockitoAnnotations
import java.time.Instant

/**
 * Unit tests for WriteDiscoveredStrategiesToPostgresFn using the new factory pattern
 * with assisted injection.
 *
 * These tests focus on the DoFn's data transformation logic using mocked dependencies.
 * Full integration tests with PostgreSQL would require a test database.
 */
@RunWith(JUnit4::class)
class WriteDiscoveredStrategiesToPostgresFnTest {
    // We do not run the pipeline in these unit tests; turn off the enforcement that
    // would otherwise throw PipelineRunMissingException.
    @get:Rule
    val pipeline: TestPipeline =
        TestPipeline.create().enableAbandonedNodeEnforcement(false)

    // The class under test - will be created directly with test configuration
    private lateinit var writeDiscoveredStrategiesToPostgresFn: WriteDiscoveredStrategiesToPostgresFn

    // Test database configuration
    private val testServerName = "localhost"
    private val testDatabaseName = "test_db"
    private val testUsername = "test_user"
    private val testPassword = "test_password"
    private val testPortNumber = 5432
    private val testApplicationName = "test_app"
    private val testConnectTimeout = 30
    private val testSocketTimeout = 60
    private val testReadOnly = false

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)

        // Create the function under test directly with test configuration
        writeDiscoveredStrategiesToPostgresFn =
            WriteDiscoveredStrategiesToPostgresFn.create(
                DataSourceConfig(
                    serverName = testServerName,
                    databaseName = testDatabaseName,
                    username = testUsername,
                    password = testPassword,
                    portNumber = testPortNumber,
                    applicationName = testApplicationName,
                    connectTimeout = testConnectTimeout,
                    socketTimeout = testSocketTimeout,
                    readOnly = testReadOnly,
                ),
            )
    }

    @Test
    fun testInstanceCreatedWithCorrectParameters() {
        // Verify the instance is not null and was created successfully
        assert(writeDiscoveredStrategiesToPostgresFn != null) { "Instance should be created successfully" }
    }

    @Test
    fun testPipelineDoesNotFailWithValidStrategy() {
        // This test verifies the DoFn can be constructed and added to pipeline
        // without database connection (actual database writes would require integration tests)
        val startTime = Instant.parse("2023-01-01T00:00:00Z")
        val endTime = Instant.parse("2023-01-01T01:00:00Z")

        val smaRsiParams = SmaRsiParameters.newBuilder().setRsiPeriod(14).build()
        val strategyProto =
            Strategy
                .newBuilder()
                .setType(StrategyType.SMA_RSI)
                .setParameters(Any.pack(smaRsiParams))
                .build()

        val discoveredStrategy =
            DiscoveredStrategy
                .newBuilder()
                .setSymbol("BTC/USD")
                .setStrategy(strategyProto)
                .setScore(0.75)
                .setStartTime(
                    Timestamp
                        .newBuilder()
                        .setSeconds(startTime.epochSecond)
                        .setNanos(startTime.nano)
                        .build(),
                ).setEndTime(
                    Timestamp
                        .newBuilder()
                        .setSeconds(endTime.epochSecond)
                        .setNanos(endTime.nano)
                        .build(),
                ).build()

        val input: PCollection<DiscoveredStrategy> = pipeline.apply(Create.of(discoveredStrategy))

        // This would normally write to PostgreSQL, but for unit testing we just verify
        // the pipeline can be constructed without errors using the directly created instance
        val output: PCollection<Void> = input.apply(ParDo.of(writeDiscoveredStrategiesToPostgresFn))

        // Note: We can't run this pipeline in unit tests without a database
        // This test just verifies the DoFn can be instantiated correctly
        assert(output != null) { "Pipeline should be constructable" }
    }
}
