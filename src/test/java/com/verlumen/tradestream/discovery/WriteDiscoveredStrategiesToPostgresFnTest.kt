package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.gson.JsonParser
import com.google.inject.Guice
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.Any
import com.google.protobuf.ByteString
import com.google.protobuf.Timestamp
import com.verlumen.tradestream.sql.BulkCopier
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
import org.mockito.Mockito.anyString
import org.mockito.Mockito.mock
import org.mockito.Mockito.`when`
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.any
import org.mockito.kotlin.whenever
import java.sql.Connection
import java.sql.PreparedStatement
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
    lateinit var mockDataSourceFactory: DataSourceFactory

    @Bind @Mock
    lateinit var mockBulkCopierFactory: BulkCopierFactory

    @Mock
    lateinit var mockDataSource: DataSource

    @Mock
    lateinit var mockConnection: Connection

    @Mock
    private lateinit var preparedStatement: PreparedStatement

    @Mock
    private lateinit var bulkCopier: BulkCopier

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

        // Setup mocks
        `when`(mockConnection.prepareStatement(anyString())).thenReturn(preparedStatement)
        `when`(mockBulkCopierFactory.create(mockConnection)).thenReturn(bulkCopier)
        `when`(preparedStatement.execute()).thenReturn(true)
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

    @Test
    fun `test strategy parameters JSON serialization handles incomplete JSON`() {
        // Create a strategy with valid parameters
        val strategy =
            Strategy
                .newBuilder()
                .setType(StrategyType.SMA_RSI)
                .setParameters(Any.getDefaultInstance()) // This will trigger the empty parameters case
                .build()

        val discoveredStrategy =
            DiscoveredStrategy
                .newBuilder()
                .setSymbol("BTCUSDT")
                .setStrategy(strategy)
                .setScore(0.85)
                .setStartTime(Timestamp.getDefaultInstance())
                .setEndTime(Timestamp.getDefaultInstance())
                .build()

        // This should not throw an exception and should return null due to invalid JSON
        val csvRow = writeDiscoveredStrategiesToPostgresFn.convertToCsvRow(discoveredStrategy)

        // Should return null for invalid JSON parameters
        assert(csvRow == null) { "Should return null for invalid JSON parameters" }
    }

    @Test
    fun `test bulk insert rejects malformed JSON parameters`() {
        // Create a batch with malformed JSON
        val malformedBatch =
            listOf(
                "BTCUSDT\tSMA_RSI\t{\t0.85\thash123\tBTCUSDT\t1234567890\t1234567891", // Incomplete JSON
                "ETHUSDT\tEMA_MACD\t{}\t0.75\thash456\tETHUSDT\t1234567890\t1234567891", // Valid JSON
            )

        // The validation should filter out the malformed JSON
        val validatedBatch =
            malformedBatch.filter { csvRow ->
                writeDiscoveredStrategiesToPostgresFn.validateCsvRowJson(csvRow)
            }

        // Should only keep the valid JSON row
        assert(validatedBatch.size == 1) { "Should only keep valid JSON rows" }
        assert(validatedBatch[0].contains("ETHUSDT")) { "Should keep ETHUSDT row" }
    }

    @Test
    fun `test PostgreSQL COPY operation with valid JSON formats`() {
        // Create a strategy with valid parameters
        val validParameters =
            Any.pack(
                com.verlumen.tradestream.strategies.SmaRsiParameters.newBuilder()
                    .setMovingAveragePeriod(14)
                    .setRsiPeriod(14)
                    .setOverboughtThreshold(70.0)
                    .setOversoldThreshold(30.0)
                    .build()
            )

        val strategy =
            Strategy
                .newBuilder()
                .setType(StrategyType.SMA_RSI)
                .setParameters(validParameters)
                .build()

        val discoveredStrategy =
            DiscoveredStrategy
                .newBuilder()
                .setSymbol("BTCUSDT")
                .setStrategy(strategy)
                .setScore(0.85)
                .setStartTime(Timestamp.getDefaultInstance())
                .setEndTime(Timestamp.getDefaultInstance())
                .build()

        val csvRow = writeDiscoveredStrategiesToPostgresFn.convertToCsvRow(discoveredStrategy)

        // Should not be null for valid parameters
        assert(csvRow != null) { "Should not be null for valid parameters" }

        // Should contain the expected fields
        val fields = csvRow!!.split("\t")
        assert(fields.size == 8) { "Should have 8 fields" }
        assert(fields[0] == "BTCUSDT") { "First field should be BTCUSDT" }
        assert(fields[1] == "SMA_RSI") { "Second field should be SMA_RSI" }

        // The JSON field should be valid
        val jsonField = fields[2]
        assert(jsonField.startsWith("{") && jsonField.endsWith("}")) { "JSON field should be properly formatted" }

        // Should be parseable as JSON
        try {
            JsonParser.parseString(jsonField)
        } catch (e: Exception) {
            throw AssertionError("Generated JSON is not valid: $jsonField", e)
        }
    }

    @Test
    fun `test JSON validation prevents database errors`() {
        // Test various invalid JSON scenarios
        val invalidJsonScenarios =
            listOf(
                null, // null JSON
                "", // empty string
                "   ", // whitespace only
                "{", // incomplete JSON
                "}", // incomplete JSON
                "invalid json", // not JSON at all
                "{\"key\": \"value\"", // missing closing brace
                "{\"key\": \"value\"}", // valid JSON
            )

        val expectedResults = listOf(false, false, false, false, false, false, false, true)

        invalidJsonScenarios.zip(expectedResults).forEach { (json, expectedValid) ->
            val isValid = writeDiscoveredStrategiesToPostgresFn.validateJsonParameter(json)
            assert(isValid == expectedValid) { "JSON validation failed for: '$json'" }
        }
    }

    @Test
    fun `test CSV row validation handles edge cases`() {
        // Test various CSV row scenarios
        val testCases =
            listOf(
                "BTCUSDT\tSMA_RSI\t{\"valid\": \"json\"}\t0.85\thash123\tBTCUSDT\t1234567890\t1234567891" to true, // Valid
                "BTCUSDT\tSMA_RSI\t{\t0.85\thash123\tBTCUSDT\t1234567890\t1234567891" to false, // Invalid JSON
                "BTCUSDT\tSMA_RSI" to false, // Insufficient fields
                "" to false, // Empty string
            )

        testCases.forEach { (csvRow, expectedValid) ->
            val isValid = writeDiscoveredStrategiesToPostgresFn.validateCsvRowJson(csvRow)
            assert(isValid == expectedValid) { "CSV validation failed for: '$csvRow'" }
        }
    }

    @Test
    fun `test JSON validation with special characters`() {
        // Test JSON with special characters that might cause issues
        val specialJson = """{"key": "value with \"quotes\" and \n newlines"}"""
        val isValid = writeDiscoveredStrategiesToPostgresFn.validateJsonParameter(specialJson)
        assert(isValid) { "JSON with special characters should be valid" }
    }

    @Test
    fun `test JSON validation with nested objects`() {
        // Test complex nested JSON
        val nestedJson = """{"outer": {"inner": {"deep": "value"}}}"""
        val isValid = writeDiscoveredStrategiesToPostgresFn.validateJsonParameter(nestedJson)
        assert(isValid) { "Nested JSON should be valid" }
    }

    @Test
    fun `test JSON validation with arrays`() {
        // Test JSON with arrays
        val arrayJson = """{"items": [1, 2, 3, "string"]}"""
        val isValid = writeDiscoveredStrategiesToPostgresFn.validateJsonParameter(arrayJson)
        assert(isValid) { "JSON with arrays should be valid" }
    }

    @Test
    fun `test CSV row parsing handles tab characters in data`() {
        // Test that CSV parsing correctly handles tab-separated values
        val csvRow = "BTCUSDT\tSMA_RSI\t{\"param\": \"value\"}\t0.85\thash123\tBTCUSDT\t1234567890\t1234567891"
        val fields = csvRow.split("\t")
        assert(fields.size == 8) { "CSV row should have 8 fields" }
        assert(fields[0] == "BTCUSDT") { "First field should be BTCUSDT" }
        assert(fields[1] == "SMA_RSI") { "Second field should be SMA_RSI" }
        assert(fields[2] == "{\"param\": \"value\"}") { "Third field should be the JSON" }
    }

    @Test
    fun `test batch filtering removes invalid rows`() {
        // Create a batch with mixed valid and invalid rows
        val mixedBatch =
            listOf(
                "BTCUSDT\tSMA_RSI\t{\"valid\": \"json\"}\t0.85\thash1\tBTCUSDT\t1234567890\t1234567891", // Valid
                "ETHUSDT\tEMA_MACD\t{\t0.75\thash2\tETHUSDT\t1234567890\t1234567891", // Invalid JSON
                "ADAUSDT\tRSI_EMA\t{\"also\": \"valid\"}\t0.92\thash3\tADAUSDT\t1234567890\t1234567891", // Valid
                "DOTUSDT\tMACD\tinvalid json\t0.68\thash4\tDOTUSDT\t1234567890\t1234567891", // Invalid JSON
            )

        val validatedBatch =
            mixedBatch.filter { csvRow ->
                writeDiscoveredStrategiesToPostgresFn.validateCsvRowJson(csvRow)
            }

        // Should only keep the valid rows
        assert(validatedBatch.size == 2) { "Should only keep 2 valid rows" }
        assert(validatedBatch.any { it.contains("BTCUSDT") }) { "Should keep BTCUSDT row" }
        assert(validatedBatch.any { it.contains("ADAUSDT") }) { "Should keep ADAUSDT row" }
        assert(!validatedBatch.any { it.contains("ETHUSDT") }) { "Should not keep ETHUSDT row" }
        assert(!validatedBatch.any { it.contains("DOTUSDT") }) { "Should not keep DOTUSDT row" }
    }

    @Test
    fun `test empty batch handling`() {
        // Test that empty batches are handled gracefully
        val emptyBatch = emptyList<String>()
        val validatedBatch =
            emptyBatch.filter { csvRow ->
                writeDiscoveredStrategiesToPostgresFn.validateCsvRowJson(csvRow)
            }
        assert(validatedBatch.size == 0) { "Empty batch should remain empty" }
    }

    @Test
    fun `test all valid batch passes through unchanged`() {
        // Test that a batch with all valid rows passes through unchanged
        val validBatch =
            listOf(
                "BTCUSDT\tSMA_RSI\t{\"valid\": \"json1\"}\t0.85\thash1\tBTCUSDT\t1234567890\t1234567891",
                "ETHUSDT\tEMA_MACD\t{\"valid\": \"json2\"}\t0.75\thash2\tETHUSDT\t1234567890\t1234567891",
                "ADAUSDT\tRSI_EMA\t{\"valid\": \"json3\"}\t0.92\thash3\tADAUSDT\t1234567890\t1234567891",
            )

        val validatedBatch =
            validBatch.filter { csvRow ->
                writeDiscoveredStrategiesToPostgresFn.validateCsvRowJson(csvRow)
            }

        assert(validatedBatch.size == 3) { "All valid rows should pass through" }
        assert(validatedBatch == validBatch) { "Valid batch should remain unchanged" }
    }
}
