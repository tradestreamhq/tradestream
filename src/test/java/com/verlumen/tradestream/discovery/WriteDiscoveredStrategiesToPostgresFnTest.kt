package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.Any
import com.google.protobuf.ByteString
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
import org.apache.beam.sdk.values.PCollection
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
import org.mockito.Mockito.mock
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
    fun testInstanceCreatedWithCorrectParameters() {
        // Verify the instance is not null and was created successfully
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

    @Test
    fun testBatchIsInitializedAfterSetup() {
        // Before setup, batch should be null
        val batchField = WriteDiscoveredStrategiesToPostgresFn::class.java.getDeclaredField("batch")
        batchField.isAccessible = true
        batchField.set(writeDiscoveredStrategiesToPostgresFn, null)

        // Call setup
        val setupMethod = WriteDiscoveredStrategiesToPostgresFn::class.java.getDeclaredMethod("setup")
        setupMethod.isAccessible = true
        setupMethod.invoke(writeDiscoveredStrategiesToPostgresFn)

        // After setup, batch should be a ConcurrentLinkedQueue and empty
        val batchValue = batchField.get(writeDiscoveredStrategiesToPostgresFn)
        assert(batchValue is java.util.concurrent.ConcurrentLinkedQueue<*>) { "Batch should be initialized as ConcurrentLinkedQueue" }
        assert((batchValue as java.util.concurrent.ConcurrentLinkedQueue<*>).isEmpty()) { "Batch should be empty after setup" }
    }

    @Test
    fun testCsvRowGenerationWithInvalidAny() {
        val bulkCopierFactory = mock(BulkCopierFactory::class.java)
        val dataSourceFactory = mock(DataSourceFactory::class.java)
        val dataSourceConfig = mock(DataSourceConfig::class.java)
        val fn = WriteDiscoveredStrategiesToPostgresFn(bulkCopierFactory, dataSourceFactory, dataSourceConfig)
        val invalidAny =
            Any
                .newBuilder()
                .setTypeUrl("type.googleapis.com/unknown.UnknownParameters")
                .setValue(ByteString.copyFromUtf8("garbage"))
                .build()
        val element =
            DiscoveredStrategy
                .newBuilder()
                .setSymbol("BTCUSD")
                .setStrategy(
                    Strategy
                        .newBuilder()
                        .setType(StrategyType.UNSPECIFIED)
                        .setParameters(invalidAny)
                        .build(),
                ).setScore(1.0)
                .setStartTime(Timestamp.newBuilder().setSeconds(0).build())
                .setEndTime(Timestamp.newBuilder().setSeconds(1).build())
                .build()
        val method = WriteDiscoveredStrategiesToPostgresFn::class.java.getDeclaredMethod("convertToCsvRow", DiscoveredStrategy::class.java)
        method.isAccessible = true
        val row = method.invoke(fn, element) as String
        val paramsColumn = row.split("\t")[2]
        assert(paramsColumn.contains("base64_data")) { "Parameters column should contain base64_data for invalid Any, got: $paramsColumn" }
        assert(paramsColumn.contains("type_url")) { "Parameters column should contain type_url for invalid Any, got: $paramsColumn" }
        assert(
            paramsColumn.contains("unknown.UnknownParameters"),
        ) { "Parameters column should contain the correct type_url, got: $paramsColumn" }
    }
}
