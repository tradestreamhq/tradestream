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
import org.mockito.ArgumentMatchers.eq // For eq() matcher
import org.mockito.Mock
import org.mockito.Mockito.`when`
import org.mockito.Mockito.anyString
import org.mockito.MockitoAnnotations
import java.time.Instant

@RunWith(JUnit4::class)
class InfluxDbCandleFetcherTest {
    // AI Note: For improved testability, InfluxDBClient should be injected into InfluxDbCandleFetcher.
    // The following test uses reflection to inject a mock client, which is not ideal but fulfills the prompt.
    // A cleaner approach involves constructor-based Dependency Injection.

    @Mock private lateinit var mockInfluxDBClient: InfluxDBClient

    @Mock private lateinit var mockQueryApi: QueryApi

    private val testUrl = "http://fake-influx:8086"
    private val testToken = "fake-token"
    private val testOrg = "fake-org"
    private val testBucket = "fake-bucket"

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        `when`(mockInfluxDBClient.queryApi).thenReturn(mockQueryApi)
    }

    @Test
    fun fetchCandles_returnsParsedCandles_whenQuerySucceeds() {
        // Arrange
        val symbol = "BTC/USD"
        val startTime = Timestamps.fromMillis(Instant.parse("2023-01-01T00:00:00Z").toEpochMilli())
        val endTime = Timestamps.fromMillis(Instant.parse("2023-01-01T01:00:00Z").toEpochMilli())

        val mockRecord1Time = Instant.parse("2023-01-01T00:00:00Z")
        val mockRecord1 = mock(FluxRecord::class.java)
        `when`(mockRecord1.time).thenReturn(mockRecord1Time)
        `when`(mockRecord1.getValueByKey("open")).thenReturn(100.0)
        `when`(mockRecord1.getValueByKey("high")).thenReturn(105.0)
        `when`(mockRecord1.getValueByKey("low")).thenReturn(99.0)
        `when`(mockRecord1.getValueByKey("close")).thenReturn(102.0)
        `when`(mockRecord1.getValueByKey("volume")).thenReturn(10.0)

        val mockTable1 = mock(FluxTable::class.java)
        `when`(mockTable1.records).thenReturn(listOf(mockRecord1))
        `when`(mockQueryApi.query(anyString(), eq(testOrg))).thenReturn(listOf(mockTable1))

        // Testable fetcher using reflection to inject the mock client
        val testableFetcher =
            object : InfluxDbCandleFetcher(testUrl, testToken, testOrg, testBucket) {
                init {
                    val clientField = InfluxDbCandleFetcher::class.java.getDeclaredField("influxDBClient")
                    clientField.isAccessible = true
                    clientField.set(this, mockInfluxDBClient) // Use the class-level mock
                }
            }

        // Act
        val candles = testableFetcher.fetchCandles(symbol, startTime, endTime)

        // Assert
        assertThat(candles).hasSize(1)
        val candle = candles[0]
        assertThat(candle.currencyPair).isEqualTo(symbol)
        assertThat(Timestamps.toMillis(candle.timestamp)).isEqualTo(mockRecord1Time.toEpochMilli())
        assertThat(candle.open).isEqualTo(100.0)
        assertThat(candle.high).isEqualTo(105.0)
        assertThat(candle.low).isEqualTo(99.0)
        assertThat(candle.close).isEqualTo(102.0)
        assertThat(candle.volume).isEqualTo(10.0)
        
        testableFetcher.close()
    }

    @Test
    fun fetchCandles_handlesNullRecordTimeGracefully() {
        // Arrange
        val symbol = "ETH/USD"
        val startTime = Timestamps.fromMillis(Instant.parse("2023-02-01T00:00:00Z").toEpochMilli())
        val endTime = Timestamps.fromMillis(Instant.parse("2023-02-01T01:00:00Z").toEpochMilli())

        val mockRecordNullTime = mock(FluxRecord::class.java)
        `when`(mockRecordNullTime.time).thenReturn(null) // Simulate null time

        val mockTable = mock(FluxTable::class.java)
        `when`(mockTable.records).thenReturn(listOf(mockRecordNullTime))
        `when`(mockQueryApi.query(anyString(), eq(testOrg))).thenReturn(listOf(mockTable))

        val testableFetcher = object : InfluxDbCandleFetcher(testUrl, testToken, testOrg, testBucket) {
            init {
                val clientField = InfluxDbCandleFetcher::class.java.getDeclaredField("influxDBClient")
                clientField.isAccessible = true
                clientField.set(this, mockInfluxDBClient)
            }
        }

        // Act
        val candles = testableFetcher.fetchCandles(symbol, startTime, endTime)

        // Assert
        assertThat(candles).isEmpty() // Record with null time should be skipped
        testableFetcher.close()
    }
    @Test
    fun fetchCandles_handlesRecordParsingExceptionGracefully() {
        // Arrange
        val symbol = "ADA/USD"
        val startTime = Timestamps.fromMillis(Instant.parse("2023-03-01T00:00:00Z").toEpochMilli())
        val endTime = Timestamps.fromMillis(Instant.parse("2023-03-01T01:00:00Z").toEpochMilli())

        val mockRecordValidTime = Instant.parse("2023-03-01T00:05:00Z")
        val mockRecordMalformed = mock(FluxRecord::class.java)
        `when`(mockRecordMalformed.time).thenReturn(mockRecordValidTime)
        `when`(mockRecordMalformed.getValueByKey("open")).thenThrow(ClassCastException("Simulated parsing error")) // Malformed data

        val mockTable = mock(FluxTable::class.java)
        `when`(mockTable.records).thenReturn(listOf(mockRecordMalformed))
        `when`(mockQueryApi.query(anyString(), eq(testOrg))).thenReturn(listOf(mockTable))

        val testableFetcher =
            object : InfluxDbCandleFetcher(testUrl, testToken, testOrg, testBucket) {
                init {
                    val clientField = InfluxDbCandleFetcher::class.java.getDeclaredField("influxDBClient")
                    clientField.isAccessible = true
                    clientField.set(this, mockInfluxDBClient)
                }
            }

        // Act
        val candles = testableFetcher.fetchCandles(symbol, startTime, endTime)

        // Assert
        assertThat(candles).isEmpty() // Record with parsing error should be skipped
        testableFetcher.close()
    }

    @Test
    fun fetchCandles_returnsEmptyList_whenQueryApiThrowsException() {
        // Arrange
        val symbol = "XRP/USD"
        val startTime = Timestamps.fromMillis(Instant.parse("2023-04-01T00:00:00Z").toEpochMilli())
        val endTime = Timestamps.fromMillis(Instant.parse("2023-04-01T01:00:00Z").toEpochMilli())

        `when`(mockQueryApi.query(anyString(), eq(testOrg))).thenThrow(RuntimeException("Simulated InfluxDB error"))

        val testableFetcher =
            object : InfluxDbCandleFetcher(testUrl, testToken, testOrg, testBucket) {
                init {
                    val clientField = InfluxDbCandleFetcher::class.java.getDeclaredField("influxDBClient")
                    clientField.isAccessible = true
                    clientField.set(this, mockInfluxDBClient)
                }
            }
        // Act
        val candles = testableFetcher.fetchCandles(symbol, startTime, endTime)

        // Assert
        assertThat(candles).isEmpty()
        testableFetcher.close()
    }
}
