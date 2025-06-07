package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.Any
import com.google.protobuf.Timestamp
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
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.whenever
import java.sql.Connection
import java.time.Instant
import javax.sql.DataSource

/**
 * Unit tests for WriteDiscoveredStrategiesToPostgresFn using Guice injection.
 *
 * These tests focus on the DoFn's data transformation logic using mocked dependencies.
 * Full integration tests with PostgreSQL would require a test database.
 */
@RunWith(JUnit4::class)
class WriteDiscoveredStrategiesToPostgresFnTest {
    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create()

    // Use BoundFieldModule to inject this mock
    @Bind @Mock
    lateinit var mockDataSource: DataSource

    @Mock
    lateinit var mockConnection: Connection

    // The class under test - will be injected by Guice
    @Inject
    lateinit var writeDiscoveredStrategiesToPostgresFn: WriteDiscoveredStrategiesToPostgresFn

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)

        // Create Guice injector with BoundFieldModule to inject the test fixture
        val injector = Guice.createInjector(BoundFieldModule.of(this))
        injector.injectMembers(this)

        // Setup mock behavior
        whenever(mockDataSource.connection).thenReturn(mockConnection)
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
        // the pipeline can be constructed without errors using the injected instance
        val output: PCollection<Void> = input.apply(ParDo.of(writeDiscoveredStrategiesToPostgresFn))

        // Note: We can't run this pipeline in unit tests without a database
        // This test just verifies the DoFn can be instantiated correctly via Guice
        assert(output != null) { "Pipeline should be constructable" }
    }
}
