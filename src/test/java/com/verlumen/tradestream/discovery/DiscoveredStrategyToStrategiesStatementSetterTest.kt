package com.verlumen.tradestream.discovery

import com.google.protobuf.Any
import com.google.protobuf.Timestamp
import com.google.protobuf.util.JsonFormat
import com.verlumen.tradestream.discovery.proto.Discovery.DiscoveredStrategy
import com.verlumen.tradestream.strategies.SmaRsiParameters
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategyType
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
import org.mockito.Mockito.*
import org.mockito.MockitoAnnotations
import java.sql.PreparedStatement
import java.time.Instant

@RunWith(JUnit4::class)
class DiscoveredStrategyToStrategiesStatementSetterTest {
    @Mock
    private lateinit var mockPreparedStatement: PreparedStatement

    private lateinit var setter: DiscoveredStrategyToStrategiesStatementSetter

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        setter = DiscoveredStrategyToStrategiesStatementSetter()
    }

    @Test
    fun testSetParameters_success() {
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

        val expectedParamsJson = JsonFormat.printer().print(paramsAny)
        val expectedHashInput = "BTC/USD:SMA_RSI:${paramsAny.typeUrl}:${paramsAny.value.toStringUtf8()}"
        // Using a simple hashCode for testing, replace with actual SHA256 if needed for verification
        val expectedStrategyHash = expectedHashInput.hashCode().toString()

        setter.setParameters(discoveredStrategy, mockPreparedStatement)

        verify(mockPreparedStatement).setString(1, "BTC/USD") // symbol
        verify(mockPreparedStatement).setString(2, "SMA_RSI") // strategy_type
        verify(mockPreparedStatement).setString(3, expectedParamsJson) // parameters (jsonb)
        verify(mockPreparedStatement).setDouble(4, 0.75) // current_score
        verify(mockPreparedStatement).setString(5, expectedStrategyHash) // strategy_hash
        verify(mockPreparedStatement).setString(6, "BTC/USD") // discovery_symbol
        verify(mockPreparedStatement).setTimestamp(7, java.sql.Timestamp.from(startTime)) // discovery_start_time
        verify(mockPreparedStatement).setTimestamp(8, java.sql.Timestamp.from(endTime)) // discovery_end_time
    }

    @Test
    fun testSetParameters_anySerializationError_defaultsToJsonEmptyObject() {
        val startTime = Instant.parse("2023-01-01T00:00:00Z")
        val endTime = Instant.parse("2023-01-01T01:00:00Z")

        // Create an Any object that JsonFormat cannot print (e.g. by not being a valid message)
        // For this test, we'll mock the printer to throw an exception.
        val mockPrinter = mock(JsonFormat.Printer::class.java)
        `when`(mockPrinter.print(any(Any::class.java))).thenThrow(InvalidProtocolBufferException("Simulated error"))

        // To inject this mock, we would ideally modify the class or use a more complex setup.
        // For this unit test, we'll assume the logger catches it and sets "{}"
        // We can verify the logger interaction if we could inject a mock logger.
        // Here, we'll just assert that "{}" is set for parameters.

        val strategyProto =
            Strategy
                .newBuilder()
                .setType(StrategyType.UNSPECIFIED) // or any type
                .setParameters(
                    Any
                        .newBuilder()
                        .setTypeUrl(
                            "type.googleapis.com/InvalidType",
                        ).setValue(
                            com.google.protobuf.ByteString
                                .copyFromUtf8("invalid"),
                        ).build(),
                ) // Malformed Any
                .build()

        val discoveredStrategy =
            DiscoveredStrategy
                .newBuilder()
                .setSymbol("ERR/SYM")
                .setStrategy(strategyProto)
                .setScore(0.1)
                .setStartTime(Timestamp.newBuilder().setSeconds(startTime.epochSecond).build())
                .setEndTime(Timestamp.newBuilder().setSeconds(endTime.epochSecond).build())
                .build()

        val expectedHashInput = "ERR/SYM:UNSPECIFIED:type.googleapis.com/InvalidType:invalid"
        val expectedStrategyHash = expectedHashInput.hashCode().toString()

        // We need to use a setter where we can control JsonFormat.printer() or verify logging.
        // For simplicity, we'll check the outcome assuming the internal catch block works as intended.
        setter.setParameters(discoveredStrategy, mockPreparedStatement)

        verify(mockPreparedStatement).setString(1, "ERR/SYM")
        verify(mockPreparedStatement).setString(2, "UNSPECIFIED")
        verify(mockPreparedStatement).setString(3, "{}") // Expect default JSON
        verify(mockPreparedStatement).setDouble(4, 0.1)
        verify(mockPreparedStatement).setString(5, expectedStrategyHash) // Hash might be based on malformed data
        verify(mockPreparedStatement).setString(6, "ERR/SYM")
        verify(mockPreparedStatement).setTimestamp(7, java.sql.Timestamp.from(startTime))
        verify(mockPreparedStatement).setTimestamp(8, java.sql.Timestamp.from(endTime))
    }
}
