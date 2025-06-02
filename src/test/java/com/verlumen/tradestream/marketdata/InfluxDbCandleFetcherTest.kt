package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.util.Timestamps
import com.influxdb.client.InfluxDBClient
import com.influxdb.client.QueryApi
import com.influxdb.query.FluxRecord
import com.influxdb.query.FluxTable
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.ArgumentMatchers.eq
import org.mockito.Mock
import org.mockito.Mockito.anyString
import org.mockito.Mockito.mock
import org.mockito.Mockito.verify
import org.mockito.Mockito.`when`
import org.mockito.MockitoAnnotations
import java.time.Instant

@RunWith(JUnit4::class)
class InfluxDbCandleFetcherTest {
    @Mock private lateinit var mockInfluxDBClient: InfluxDBClient

    @Mock private lateinit var mockQueryApi: QueryApi

    private val testUrl = "http://test-influxdb:8086"
    private val testToken = "test-token-123"
    private val testOrg = "test-org"
    private val testBucket = "test-bucket"

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        `when`(mockInfluxDBClient.queryApi).thenReturn(mockQueryApi)
    }

    @Test
    fun fetchCandles_returnsParsedCandles_whenQuerySucceeds() {
        // Arrange
        val symbol = "BTC-USD"
        val startTime = Timestamps.fromMillis(Instant.parse("2025-01-01T00:00:00Z").toEpochMilli())
        val endTime = Timestamps.fromMillis(Instant.parse("2025-01-01T01:00:00Z").toEpochMilli())

        val mockTables = createMockTablesWithValidData()
        `when`(mockQueryApi.query(anyString(), eq(testOrg))).thenReturn(mockTables)

        val fetcher = createTestFetcher()

        // Act
        val candles = fetcher.fetchCandles(symbol, startTime, endTime)

        // Assert
        assertThat(candles).hasSize(2)
        // Verify first candle
        val firstCandle = candles[0]
        assertThat(firstCandle.currencyPair).isEqualTo(symbol)
        assertThat(firstCandle.open).isEqualTo(50000.0)
        assertThat(firstCandle.high).isEqualTo(51000.0)
        assertThat(firstCandle.low).isEqualTo(49500.0)
        assertThat(firstCandle.close).isEqualTo(50500.0)
        assertThat(firstCandle.volume).isEqualTo(100.5)

        // Verify second candle
        val secondCandle = candles[1]
        assertThat(secondCandle.currencyPair).isEqualTo(symbol)
        assertThat(secondCandle.open).isEqualTo(50500.0)
        assertThat(secondCandle.high).isEqualTo(52000.0)
        assertThat(secondCandle.low).isEqualTo(50000.0)
        assertThat(secondCandle.close).isEqualTo(51500.0)
        assertThat(secondCandle.volume).isEqualTo(200.75)

        // Verify the Flux query was executed
        verify(mockQueryApi).query(anyString(), eq(testOrg))
        
        fetcher.close()
    }

    @Test
    fun fetchCandles_handlesNullRecordTimeGracefully() {
        // Arrange
        val symbol = "ETH-USD"
        val startTime = Timestamps.fromMillis(Instant.parse("2025-01-01T00:00:00Z").toEpochMilli())
        val endTime = Timestamps.fromMillis(Instant.parse("2025-01-01T01:00:00Z").toEpochMilli())

        val mockTables = createMockTablesWithNullTime()
        `when`(mockQueryApi.query(anyString(), eq(testOrg))).thenReturn(mockTables)

        val fetcher = createTestFetcher()

        // Act
        val candles = fetcher.fetchCandles(symbol, startTime, endTime)

        // Assert
        assertThat(candles).isEmpty() // Records with null time should be skipped
        fetcher.close()
    }

    @Test
    fun fetchCandles_handlesRecordParsingExceptionGracefully() {
        // Arrange
        val symbol = "ADA-USD"
        val startTime = Timestamps.fromMillis(Instant.parse("2025-01-01T00:00:00Z").toEpochMilli())
        val endTime = Timestamps.fromMillis(Instant.parse("2025-01-01T01:00:00Z").toEpochMilli())

        val mockTables = createMockTablesWithMalformedData()
        `when`(mockQueryApi.query(anyString(), eq(testOrg))).thenReturn(mockTables)

        val fetcher = createTestFetcher()

        // Act
        val candles = fetcher.fetchCandles(symbol, startTime, endTime)

        // Assert
        assertThat(candles).isEmpty() // Records with parsing errors should be skipped
        fetcher.close()
    }

    @Test
    fun fetchCandles_returnsEmptyList_whenQueryApiThrowsException() {
        // Arrange
        val symbol = "SOL-USD"
        val startTime = Timestamps.fromMillis(Instant.parse("2025-01-01T00:00:00Z").toEpochMilli())
        val endTime = Timestamps.fromMillis(Instant.parse("2025-01-01T01:00:00Z").toEpochMilli())

        `when`(mockQueryApi.query(anyString(), eq(testOrg)))
            .thenThrow(RuntimeException("InfluxDB connection timeout"))

        val fetcher = createTestFetcher()

        // Act
        val candles = fetcher.fetchCandles(symbol, startTime, endTime)

        // Assert
        assertThat(candles).isEmpty()
        fetcher.close()
    }

    @Test
    fun fetchCandles_buildsCorrectFluxQuery_withProvidedParameters() {
        // Arrange
        val symbol = "DOGE-USD"
        val startTime = Timestamps.fromMillis(Instant.parse("2025-06-01T12:00:00Z").toEpochMilli())
        val endTime = Timestamps.fromMillis(Instant.parse("2025-06-01T13:00:00Z").toEpochMilli())
        
        `when`(mockQueryApi.query(anyString(), eq(testOrg))).thenReturn(emptyList())

        val fetcher = createTestFetcher()

        // Act
        fetcher.fetchCandles(symbol, startTime, endTime)

        // Assert - Verify that the query contains expected elements
        verify(mockQueryApi).query(
            org.mockito.ArgumentMatchers.argThat { query: String ->
                query.contains("from(bucket: \"$testBucket\")") &&
                query.contains("r.currency_pair == \"$symbol\"") &&
                query.contains("r._measurement == \"candles\"") &&
                query.contains("2025-06-01T12:00:00Z") &&
                query.contains("2025-06-01T13:00:00Z")
            },
            eq(testOrg)
        )
        
        fetcher.close()
    }

    // Helper methods to create test data

    private fun createTestFetcher(): InfluxDbCandleFetcher =
        object : InfluxDbCandleFetcher(testUrl, testToken, testOrg, testBucket) {
            init {
                // Use reflection to inject the mock client
                val clientField = InfluxDbCandleFetcher::class.java.getDeclaredField("influxDBClient")
                clientField.isAccessible = true
                clientField.set(this, mockInfluxDBClient)
            }
        }

    private fun createMockTablesWithValidData(): List<FluxTable> {
        val record1 =
            createMockRecord(
                time = Instant.parse("2025-01-01T00:00:00Z"),
                open = 50000.0,
                high = 51000.0,
                low = 49500.0,
                close = 50500.0,
                volume = 100.5,
            )
        val record2 =
            createMockRecord(
                time = Instant.parse("2025-01-01T00:01:00Z"),
                open = 50500.0,
                high = 52000.0,
                low = 50000.0,
                close = 51500.0,
                volume = 200.75,
            )

        val mockTable = mock(FluxTable::class.java)
        `when`(mockTable.records).thenReturn(listOf(record1, record2))
        return listOf(mockTable)
    }

    private fun createMockTablesWithNullTime(): List<FluxTable> {
        val recordWithNullTime = mock(FluxRecord::class.java)
        `when`(recordWithNullTime.time).thenReturn(null)

        val mockTable = mock(FluxTable::class.java)
        `when`(mockTable.records).thenReturn(listOf(recordWithNullTime))
        return listOf(mockTable)
    }

    private fun createMockTablesWithMalformedData(): List<FluxTable> {
        val malformedRecord = mock(FluxRecord::class.java)
        `when`(malformedRecord.time).thenReturn(Instant.parse("2025-01-01T00:00:00Z"))
        `when`(malformedRecord.getValueByKey("open")).thenThrow(ClassCastException("Cannot cast to Number"))

        val mockTable = mock(FluxTable::class.java)
        `when`(mockTable.records).thenReturn(listOf(malformedRecord))
        return listOf(mockTable)
    }

    private fun createMockRecord(
        time: Instant,
        open: Double,
        high: Double,
        low: Double,
        close: Double,
        volume: Double,
    ): FluxRecord {
        val record = mock(FluxRecord::class.java)
        `when`(record.time).thenReturn(time)
        `when`(record.getValueByKey("open")).thenReturn(open)
        `when`(record.getValueByKey("high")).thenReturn(high)
        `when`(record.getValueByKey("low")).thenReturn(low)
        `when`(record.getValueByKey("close")).thenReturn(close)
        `when`(record.getValueByKey("volume")).thenReturn(volume)
        return record
    }
}
