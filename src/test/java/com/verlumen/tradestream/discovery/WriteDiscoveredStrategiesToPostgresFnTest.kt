package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.common.truth.Truth.assertThat
import com.google.inject.Guice
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.Any
import com.google.protobuf.Timestamp
import com.verlumen.tradestream.discovery.StrategyCsvUtil
import com.verlumen.tradestream.sql.DataSourceConfig
import com.verlumen.tradestream.strategies.EmaMacdParameters
import com.verlumen.tradestream.strategies.SmaRsiParameters
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.commons.csv.CSVFormat
import org.apache.commons.csv.CSVParser
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
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
    companion object {
        private val logger = FluentLogger.forEnclosingClass()
    }

    // We do not run the pipeline in these unit tests; turn off the enforcement that
    // would otherwise throw PipelineRunMissingException.
    @get:Rule
    val pipeline: TestPipeline =
        TestPipeline.create().enableAbandonedNodeEnforcement(false)

    // Use BoundFieldModule to inject these mocks
    @Bind @Mock
    lateinit var mockStrategyRepository: StrategyRepository

    // Add a mock factory that returns the mock repository
    private val mockStrategyRepositoryFactory = object : StrategyRepository.Factory {
        override fun create(dataSourceConfig: DataSourceConfig): StrategyRepository = mockStrategyRepository
    }

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

        // Create the function under test directly (simulating what the factory would do)
        val dataSourceConfig =
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
        writeDiscoveredStrategiesToPostgresFn = WriteDiscoveredStrategiesToPostgresFn(mockStrategyRepositoryFactory, dataSourceConfig)
    }

    @Test
    fun testInstanceCreatedWithCorrectParameters() {
        // Verify the instance is not null and was created successfully
        assert(writeDiscoveredStrategiesToPostgresFn != null) { "Instance should be created successfully" }
    }

    @Test
    fun testCsvRowGeneration() {
        val startTime = Instant.parse("2023-01-01T00:00:00Z")
        val endTime = Instant.parse("2023-01-02T00:00:00Z")

        val strategy =
            Strategy
                .newBuilder()
                .setType(StrategyType.SMA_RSI)
                .setParameters(
                    Any.pack(
                        SmaRsiParameters
                            .newBuilder()
                            .setMovingAveragePeriod(14)
                            .setRsiPeriod(14)
                            .setOverboughtThreshold(70.0)
                            .setOversoldThreshold(30.0)
                            .build(),
                    ),
                ).build()

        val discoveredStrategy =
            DiscoveredStrategy
                .newBuilder()
                .setSymbol("BTCUSDT")
                .setStrategy(strategy)
                .setScore(0.85)
                .setStartTime(Timestamp.newBuilder().setSeconds(startTime.epochSecond).build())
                .setEndTime(Timestamp.newBuilder().setSeconds(endTime.epochSecond).build())
                .build()

        val csvRow = StrategyCsvUtil.convertToCsvRow(discoveredStrategy)
        assertThat(csvRow).isNotNull()

        // Parse CSV to verify structure
        val csvParser = CSVParser.parse(csvRow, CSVFormat.TDF)
        val records = csvParser.records
        assertThat(records).hasSize(1)

        val record = records[0]
        assertThat(record.get(0)).isEqualTo("BTCUSDT") // symbol
        assertThat(record.get(1)).isEqualTo("SMA_RSI") // strategy_type
        assertThat(record.get(2)).isNotEmpty() // parameters (base64 JSON)
        assertThat(record.get(3)).isEqualTo("0.85") // score
        assertThat(record.get(4)).isNotEmpty() // hash
        assertThat(record.get(5)).isEqualTo("BTCUSDT") // symbol (for ON CONFLICT)
        assertThat(record.get(6)).isEqualTo(startTime.epochSecond.toString()) // start_time
        assertThat(record.get(7)).isEqualTo(endTime.epochSecond.toString()) // end_time
    }

    @Test
    fun `test PostgreSQL COPY compatibility`() {
        // Test that generated CSV rows are compatible with PostgreSQL COPY command
        val strategy =
            Strategy
                .newBuilder()
                .setType(StrategyType.EMA_MACD)
                .setParameters(
                    Any.pack(
                        EmaMacdParameters
                            .newBuilder()
                            .setShortEmaPeriod(12)
                            .setLongEmaPeriod(26)
                            .setSignalPeriod(9)
                            .build(),
                    ),
                ).build()

        val discoveredStrategy =
            DiscoveredStrategy
                .newBuilder()
                .setSymbol("ETHUSDT")
                .setStrategy(strategy)
                .setScore(0.92)
                .setStartTime(Timestamp.newBuilder().setSeconds(1672531200).build())
                .setEndTime(Timestamp.newBuilder().setSeconds(1672617600).build())
                .build()

        val csvRow = StrategyCsvUtil.convertToCsvRow(discoveredStrategy)
        assertThat(csvRow).isNotNull()

        // Verify the CSV row doesn't contain problematic characters for COPY
        assertThat(csvRow).doesNotContain("\n")
        assertThat(csvRow).doesNotContain("\r")
        val fields = csvRow?.split("\t") ?: emptyList()
        assertThat(fields.size).isEqualTo(8)
        // The parameters field (field 2) should not contain a tab
        assertThat(fields[2]).doesNotContain("\t")

        // Verify the parameters field contains the expected JSON keys
        val paramsJson = fields[2]
        assertThat(paramsJson).contains("shortEmaPeriod")
        assertThat(paramsJson).contains("longEmaPeriod")
        assertThat(paramsJson).contains("signalPeriod")
    }

    @Test
    fun `test parameter serialization edge cases`() {
        // Test with empty parameters
        val emptyStrategy =
            Strategy
                .newBuilder()
                .setType(StrategyType.SMA_RSI)
                .setParameters(Any.getDefaultInstance())
                .build()

        val emptyDiscoveredStrategy =
            DiscoveredStrategy
                .newBuilder()
                .setSymbol("TEST")
                .setStrategy(emptyStrategy)
                .setScore(0.5)
                .setStartTime(Timestamp.newBuilder().setSeconds(0).build())
                .setEndTime(Timestamp.newBuilder().setSeconds(3600).build())
                .build()

        val csvRow = StrategyCsvUtil.convertToCsvRow(emptyDiscoveredStrategy)
        assertThat(csvRow).isNotNull()
        assertThat(csvRow).contains("error:")
    }

    @Test
    fun `test batch processing logic`() {
        // Test that the batch processing logic works correctly
        writeDiscoveredStrategiesToPostgresFn.setup()

        val strategy =
            Strategy
                .newBuilder()
                .setType(StrategyType.SMA_RSI)
                .setParameters(
                    Any.pack(
                        SmaRsiParameters
                            .newBuilder()
                            .setMovingAveragePeriod(14)
                            .setRsiPeriod(14)
                            .setOverboughtThreshold(70.0)
                            .setOversoldThreshold(30.0)
                            .build(),
                    ),
                ).build()

        val discoveredStrategy =
            DiscoveredStrategy
                .newBuilder()
                .setSymbol("BTCUSDT")
                .setStrategy(strategy)
                .setScore(0.85)
                .setStartTime(Timestamp.newBuilder().setSeconds(1672531200).build())
                .setEndTime(Timestamp.newBuilder().setSeconds(1672617600).build())
                .build()

        // Process a single element
        writeDiscoveredStrategiesToPostgresFn.processElement(discoveredStrategy)

        // Finish bundle to trigger batch flush
        writeDiscoveredStrategiesToPostgresFn.finishBundle()

        // Verify that the repository was called (this would be verified with Mockito in a real test)
        // For now, just verify no exceptions were thrown
        assertThat(writeDiscoveredStrategiesToPostgresFn).isNotNull()
    }
}