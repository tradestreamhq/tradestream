package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.Guice
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.Any
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
import com.google.common.truth.Truth.assertThat
import com.verlumen.tradestream.strategies.EmaMacdParameters
import com.verlumen.tradestream.strategies.AdxStochasticParameters
import com.verlumen.tradestream.strategies.AroonMfiParameters
import com.verlumen.tradestream.strategies.IchimokuCloudParameters
import com.verlumen.tradestream.strategies.ParabolicSarParameters

/**
 * Unit tests for WriteDiscoveredStrategiesToPostgresFn using TextProto serialization.
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
    fun `test instance created with correct parameters`() {
        // Verify the instance is not null and was created successfully
        assertThat(writeDiscoveredStrategiesToPostgresFn).isNotNull()
    }

    @Test
    fun `test TextProto CSV format compatibility`() {
        // Create minimal test with known working proto
        val validParameters = Any.pack(
            SmaRsiParameters.newBuilder()
                .setMovingAveragePeriod(14)
                .setRsiPeriod(14)
                .setOverboughtThreshold(70.0)
                .setOversoldThreshold(30.0)
                .build()
        )

        val strategy = Strategy.newBuilder()
            .setType(StrategyType.SMA_RSI)
            .setParameters(validParameters)
            .build()

        val discoveredStrategy = DiscoveredStrategy.newBuilder()
            .setSymbol("BTCUSDT")
            .setStrategy(strategy)
            .setScore(0.85)
            .setStartTime(Timestamp.newBuilder().setSeconds(1640995200).build())
            .setEndTime(Timestamp.newBuilder().setSeconds(1641081600).build())
            .build()

        val csvRow = writeDiscoveredStrategiesToPostgresFn.convertToCsvRow(discoveredStrategy)
        
        // Basic validation
        assertThat(csvRow).isNotNull()
        
        val fields = csvRow!!.split("\t")
        assertThat(fields.size).isEqualTo(8)
        
        // TextProto field should not contain problematic characters
        val textProtoField = fields[2]
        assertThat(textProtoField.contains("\n")).isFalse()
        assertThat(textProtoField.contains("\r")).isFalse()
        assertThat(textProtoField.contains("\t")).isFalse()
        
        // Should contain expected field names (check actual proto definition)
        assertThat(textProtoField).isNotEmpty()
        assertThat(textProtoField).contains("movingAveragePeriod")
        assertThat(textProtoField).contains("rsiPeriod")
        assertThat(textProtoField).contains("overboughtThreshold")
        assertThat(textProtoField).contains("oversoldThreshold")
    }

    @Test
    fun `test TextProto validation`() {
        val discoveredStrategy = DiscoveredStrategy.newBuilder()
            .setSymbol("BTCUSDT")
            .setStrategy(
                Strategy.newBuilder()
                    .setType(StrategyType.SMA_RSI)
                    .setParameters(createValidParametersForStrategy(StrategyType.SMA_RSI))
                    .build()
            )
            .setScore(0.85)
            .setStartTime(Timestamp.newBuilder().setSeconds(1640995200).build())
            .setEndTime(Timestamp.newBuilder().setSeconds(1641081600).build())
            .build()
        
        val csvRow = writeDiscoveredStrategiesToPostgresFn.convertToCsvRow(discoveredStrategy)
        assertThat(csvRow).isNotNull()
        assertThat(writeDiscoveredStrategiesToPostgresFn.validateCsvRowTextProto(csvRow!!)).isTrue()
        assertThat(writeDiscoveredStrategiesToPostgresFn.validateCsvRowTextProto("invalid\tcsv")).isFalse()
        
        val invalidCsvRow = "BTCUSDT\tSMA_RSI\tinvalid_textproto\t0.85\thash\tBTCUSDT\t1234567890\t1234567891"
        assertThat(writeDiscoveredStrategiesToPostgresFn.validateCsvRowTextProto(invalidCsvRow)).isFalse()
    }

    @Test
    fun `test TextProto validation for all strategy types`() {
        val strategyTypes = listOf(
            StrategyType.SMA_RSI,
            StrategyType.EMA_MACD,
            StrategyType.ADX_STOCHASTIC,
            StrategyType.AROON_MFI,
            StrategyType.ICHIMOKU_CLOUD,
            StrategyType.PARABOLIC_SAR
        )
        
        for (strategyType in strategyTypes) {
            val discoveredStrategy = DiscoveredStrategy.newBuilder()
                .setSymbol("BTCUSDT")
                .setStrategy(
                    Strategy.newBuilder()
                        .setType(strategyType)
                        .setParameters(createValidParametersForStrategy(strategyType))
                        .build()
                )
                .setScore(0.85)
                .setStartTime(Timestamp.newBuilder().setSeconds(1234567890).build())
                .setEndTime(Timestamp.newBuilder().setSeconds(1234567891).build())
                .build()
            
            val csvRow = writeDiscoveredStrategiesToPostgresFn.convertToCsvRow(discoveredStrategy)
            assertThat(csvRow).isNotNull()
            
            val fields = csvRow!!.split("\t")
            val textProtoString = fields[2]
            assertThat(textProtoString).matches("^\\s*\\w+\\s*:\\s*[^\\s]+.*$")
        }
    }

    private fun createValidParametersForStrategy(strategyType: StrategyType): Any {
        return when (strategyType) {
            StrategyType.SMA_RSI -> Any.pack(
                SmaRsiParameters.newBuilder()
                    .setMovingAveragePeriod(14)
                    .setRsiPeriod(14)
                    .setOverboughtThreshold(70.0)
                    .setOversoldThreshold(30.0)
                    .build()
            )
            StrategyType.EMA_MACD -> Any.pack(
                EmaMacdParameters.newBuilder()
                    .setShortEmaPeriod(12)
                    .setLongEmaPeriod(26)
                    .setSignalPeriod(9)
                    .build()
            )
            StrategyType.ADX_STOCHASTIC -> Any.pack(
                AdxStochasticParameters.newBuilder()
                    .setAdxPeriod(14)
                    .setStochasticKPeriod(14)
                    .setStochasticDPeriod(3)
                    .setOverboughtThreshold(80)
                    .setOversoldThreshold(20)
                    .build()
            )
            StrategyType.AROON_MFI -> Any.pack(
                AroonMfiParameters.newBuilder()
                    .setAroonPeriod(14)
                    .setMfiPeriod(14)
                    .setOverboughtThreshold(80)
                    .setOversoldThreshold(20)
                    .build()
            )
            StrategyType.ICHIMOKU_CLOUD -> Any.pack(
                IchimokuCloudParameters.newBuilder()
                    .setTenkanSenPeriod(9)
                    .setKijunSenPeriod(26)
                    .setSenkouSpanBPeriod(52)
                    .setChikouSpanPeriod(26)
                    .build()
            )
            StrategyType.PARABOLIC_SAR -> Any.pack(
                ParabolicSarParameters.newBuilder()
                    .setAccelerationFactorStart(0.02)
                    .setAccelerationFactorIncrement(0.02)
                    .setAccelerationFactorMax(0.2)
                    .build()
            )
            else -> throw IllegalArgumentException("Unsupported strategy type: $strategyType")
        }
    }
}
