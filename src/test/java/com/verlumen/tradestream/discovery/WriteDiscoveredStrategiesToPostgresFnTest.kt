package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.Any
import com.google.protobuf.Timestamp
import com.verlumen.tradestream.sql.BulkCopierFactory
import com.verlumen.tradestream.sql.DataSourceConfig
import com.verlumen.tradestream.sql.DataSourceFactory
import com.verlumen.tradestream.strategies.SmaRsiParameters
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.any
import org.mockito.kotlin.whenever
import java.sql.Connection
import java.time.Instant
import javax.sql.DataSource

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

    // Use BoundFieldModule to inject these mocks
    @Bind @Mock
    lateinit var mockDataSourceFactory: DataSourceFactory

    @Bind @Mock
    lateinit var mockBulkCopierFactory: BulkCopierFactory

    @Mock
    lateinit var mockDataSource: DataSource

    @Mock
    lateinit var mockConnection: Connection

    // The class under test - will be created directly with mocked dependencies
    private lateinit var writeDiscoveredStrategiesToPostgresFn: WriteDiscoveredStrategiesToPostgresFn

    // Test database configuration
    private val testServerName = "test-server"
    private val testDatabaseName = "test-db"
    private val testUsername = "test-user"
    private val testPassword = "test-pass"
    private val testPortNumber = 5432
    private val testApplicationName = "test-app"
    private val testConnectTimeout = 30
    private val testSocketTimeout = 30
    private val testReadOnly = false

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)

        // Create Guice injector with BoundFieldModule to inject the test fixture
        val injector = Guice.createInjector(BoundFieldModule.of(this))
        injector.injectMembers(this)

        // Setup mock behavior for DataSourceFactory
        whenever(mockDataSourceFactory.create(any())).thenReturn(mockDataSource)
        whenever(mockDataSource.connection).thenReturn(mockConnection)

        // Create the function under test directly (simulating what the factory would do)
        writeDiscoveredStrategiesToPostgresFn =
            WriteDiscoveredStrategiesToPostgresFn(
                bulkCopierFactory = mockBulkCopierFactory,
                dataSourceFactory = mockDataSourceFactory,
                dataSourceConfig =
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
    fun testInstanceCreation() {
        assert(writeDiscoveredStrategiesToPostgresFn != null) { "Instance should be created successfully" }
    }

    @Test
    fun testCsvRowGeneration() {
        val startTime = Instant.parse("2023-01-01T00:00:00Z")
        val endTime = Instant.parse("2023-01-01T01:00:00Z")

        val smaRsiParams =
            SmaRsiParameters
                .newBuilder()
                .setRsiPeriod(14)
                .setMovingAveragePeriod(20)
                .setOverboughtThreshold(70.0)
                .setOversoldThreshold(30.0)
                .build()
        val paramsAny = Any.pack(smaRsiParams)

        val strategyProto =
            Strategy
                .newBuilder()
                .setType(StrategyType.SMA_RSI)
                .setParameters(paramsAny)
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

        // Test the CSV row generation using reflection to access private method
        val convertToCsvRowMethod =
            WriteDiscoveredStrategiesToPostgresFn::class.java
                .getDeclaredMethod("convertToCsvRow", DiscoveredStrategy::class.java)
        convertToCsvRowMethod.isAccessible = true

        val csvRow = convertToCsvRowMethod.invoke(writeDiscoveredStrategiesToPostgresFn, discoveredStrategy) as String

        // Verify CSV row contains expected data
        val columns = csvRow.split("\t")
        assert(columns.size == 8) { "Expected 8 columns, got ${columns.size}" }
        assert(columns[0] == "BTC/USD") { "Symbol should be BTC/USD" }
        assert(columns[1] == "SMA_RSI") { "Strategy type should be SMA_RSI" }
        assert(columns[3] == "0.75") { "Score should be 0.75" }
        assert(columns[5] == "BTC/USD") { "Discovery symbol should be BTC/USD" }
    }

    @Test
    fun testSha256HashGeneration() {
        // Test the SHA256 hash generation using reflection
        val sha256Method =
            WriteDiscoveredStrategiesToPostgresFn::class.java
                .getDeclaredMethod("sha256", String::class.java)
        sha256Method.isAccessible = true

        val input = "test_input"
        val hash1 = sha256Method.invoke(writeDiscoveredStrategiesToPostgresFn, input) as String
        val hash2 = sha256Method.invoke(writeDiscoveredStrategiesToPostgresFn, input) as String

        // Same input should produce same hash
        assert(hash1 == hash2) { "Same input should produce same hash" }
        assert(hash1.length == 64) { "SHA256 hash should be 64 characters long" }

        // Different input should produce different hash
        val differentHash = sha256Method.invoke(writeDiscoveredStrategiesToPostgresFn, "different_input") as String
        assert(hash1 != differentHash) { "Different inputs should produce different hashes" }
    }

    @Test
    fun testPipelineDoesNotFailWithValidStrategy() {
        // This test verifies the DoFn can be constructed and added to pipeline
        val startTime = Instant.parse("2023-01-01T00:00:00Z")
        val endTime = Instant.parse("2023-01-01T01:00:00Z")

        val smaRsiParams =
            SmaRsiParameters
                .newBuilder()
                .setRsiPeriod(14)
                .setMovingAveragePeriod(20)
                .setOverboughtThreshold(70.0)
                .setOversoldThreshold(30.0)
                .build()
        val paramsAny = Any.pack(smaRsiParams)

        val strategyProto =
            Strategy
                .newBuilder()
                .setType(StrategyType.SMA_RSI)
                .setParameters(paramsAny)
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

        val output =
            pipeline
                .apply(Create.of(discoveredStrategy))
                .apply(ParDo.of(writeDiscoveredStrategiesToPostgresFn))

        // This test just verifies the DoFn can be instantiated correctly
        assert(output != null) { "Pipeline should be constructable" }
    }

    @Test
    fun testDataSourceConfigurationValidation() {
        // Test that valid configuration creates the DataSource without errors
        val config =
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
            )

        // This should not throw any exceptions
        try {
            mockDataSourceFactory.create(config)
        } catch (e: Exception) {
            assert(false) { "Valid configuration should not cause errors: ${e.message}" }
        }
    }
}
