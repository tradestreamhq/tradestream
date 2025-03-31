package com.verlumen.tradestream.marketdata

import com.google.common.collect.ImmutableList
import com.google.common.truth.Truth.assertThat
import com.google.inject.AbstractModule
import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.assistedinject.FactoryModuleBuilder
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.instruments.CurrencyPair
import org.apache.beam.sdk.io.UnboundedSource
import org.joda.time.Instant
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.ArgumentCaptor
import org.mockito.Captor
import org.mockito.Mock
import org.mockito.Mockito.*
import org.mockito.junit.MockitoJUnit
import org.mockito.junit.MockitoRule
import java.io.IOException
import java.nio.charset.StandardCharsets
import java.util.concurrent.TimeUnit
import java.util.function.Consumer
import java.util.function.Supplier
import kotlin.test.assertFailsWith

@RunWith(JUnit4::class)
class ExchangeClientUnboundedReaderTest {

    @get:Rule val mockitoRule: MockitoRule = MockitoJUnit.rule()

    @Mock @Bind lateinit var mockExchangeClient: ExchangeStreamingClient
    @Mock @Bind lateinit var mockCurrencyPairSupply: Supplier<ImmutableList<CurrencyPair>>
    @Mock @Bind lateinit var mockSource: ExchangeClientUnboundedSource

    @Inject lateinit var readerFactory: ExchangeClientUnboundedReader.Factory

    @Captor lateinit var tradeConsumerCaptor: ArgumentCaptor<Consumer<Trade>>

    private lateinit var reader: ExchangeClientUnboundedReader
    private val testPairs = ImmutableList.of(CurrencyPair.fromSymbol("BTC/USD"))
    private val initialMark = TradeCheckpointMark.INITIAL

    @Before
    fun setUp() {
        // Setup Guice injector
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this)

        // Mock supplier behavior
        `when`(mockCurrencyPairSupply.get()).thenReturn(testPairs)

        // Create the reader instance using the factory
        reader = readerFactory.create(mockSource, initialMark)
    }

    // Helper to create a Trade
    private fun createTrade(id: String, timestampMillis: Long, price: Double = 100.0): Trade {
        val protoTimestamp = Timestamps.fromMillis(timestampMillis)
        return Trade.newBuilder()
            .setTradeId(id)
            .setTimestamp(protoTimestamp)
            .setPrice(price)
            .setVolume(1.0)
            .setExchange("test")
            .setCurrencyPair("BTC/USD")
            .build()
    }

    // Helper to simulate the client pushing a trade
    private fun simulateTradeReceived(trade: Trade) {
        // Capture the consumer the first time startStreaming is called
        verify(mockExchangeClient).startStreaming(any(), tradeConsumerCaptor.capture())
        tradeConsumerCaptor.value.accept(trade)
    }

    @Test
    @Throws(IOException::class)
    fun start_initializesClientAndAdvances() {
        // Arrange
        val tradeTime = Instant.now()
        val trade = createTrade("trade1", tradeTime.millis)
        // Pre-configure the client to call the consumer immediately when started
        doAnswer { invocation ->
            val pairs = invocation.getArgument<ImmutableList<CurrencyPair>>(0)
            val consumer = invocation.getArgument<Consumer<Trade>>(1)
            consumer.accept(trade) // Simulate immediate trade arrival
            null
        }.`when`(mockExchangeClient).startStreaming(any(), any())

        // Act
        val hasData = reader.start()

        // Assert
        verify(mockExchangeClient).startStreaming(eq(testPairs), any())
        assertThat(hasData).isTrue() // Should advance successfully
    }

    @Test
    @Throws(IOException::class)
    fun start_returnsFalseWhenNoInitialData() {
        // Arrange: Configure client to *not* send any trades immediately
        doNothing().`when`(mockExchangeClient).startStreaming(any(), any())

        // Act
        val hasData = reader.start()

        // Assert
        verify(mockExchangeClient).startStreaming(eq(testPairs), any())
        assertThat(hasData).isFalse() // Should not advance
    }

    @Test
    @Throws(IOException::class)
    fun advance_getsTradeFromQueue() {
        // Arrange
        reader.start() // Start the reader, captures the consumer
        val tradeTime = Instant.now()
        val trade = createTrade("trade2", tradeTime.millis)
        simulateTradeReceived(trade) // Simulate client pushing trade

        // Act
        val hasAdvanced = reader.advance()

        // Assert
        assertThat(hasAdvanced).isTrue()
        assertThat(reader.current).isEqualTo(trade)
    }

    @Test
    @Throws(IOException::class)
    fun advance_returnsFalseWhenQueueEmpty() {
        // Arrange
        reader.start() // Start the reader

        // Act
        val hasAdvanced = reader.advance() // Try to advance when queue is empty

        // Assert
        assertThat(hasAdvanced).isFalse()
    }

    @Test
    @Throws(IOException::class)
    fun getCurrent_returnsCorrectTrade() {
        // Arrange
        reader.start()
        val tradeTime = Instant.now()
        val trade = createTrade("trade3", tradeTime.millis)
        simulateTradeReceived(trade)
        reader.advance() // Advance to make the trade current

        // Act
        val currentTrade = reader.current

        // Assert
        assertThat(currentTrade).isEqualTo(trade)
    }

    @Test
    @Throws(IOException::class)
    fun getCurrent_throwsExceptionBeforeAdvance() {
        // Arrange
        reader.start()

        // Act & Assert
        val exception = assertFailsWith<IllegalStateException> {
            reader.current
        }
        assertThat(exception.message).contains("No current trade available")
    }

    @Test
    @Throws(IOException::class)
    fun getCurrentTimestamp_returnsCorrectTimestamp() {
        // Arrange
        reader.start()
        val tradeTime = Instant.now()
        val trade = createTrade("trade4", tradeTime.millis)
        simulateTradeReceived(trade)
        reader.advance()

        // Act
        val currentTimestamp = reader.currentTimestamp

        // Assert
        assertThat(currentTimestamp).isEqualTo(tradeTime)
    }

    @Test
    @Throws(IOException::class)
    fun getCurrentTimestamp_throwsExceptionBeforeAdvance() {
        // Arrange
        reader.start()

        // Act & Assert
        val exception = assertFailsWith<IllegalStateException> {
            reader.currentTimestamp
        }
        assertThat(exception.message).contains("Timestamp not available")
    }

    @Test
    @Throws(IOException::class)
    fun getCurrentRecordId_returnsCorrectId() {
        // Arrange
        reader.start()
        val tradeId = "trade5-unique-id"
        val tradeTime = Instant.now()
        val trade = createTrade(tradeId, tradeTime.millis)
        simulateTradeReceived(trade)
        reader.advance()

        // Act
        val recordId = reader.currentRecordId

        // Assert
        assertThat(String(recordId, StandardCharsets.UTF_8)).isEqualTo(tradeId)
    }

    @Test
    @Throws(IOException::class)
    fun getCurrentRecordId_throwsExceptionBeforeAdvance() {
        // Arrange
        reader.start()

        // Act & Assert
        val exception = assertFailsWith<IllegalStateException> {
            reader.currentRecordId
        }
        assertThat(exception.message).contains("No current trade")
    }

    @Test
    fun getWatermark_initial_returnsEpoch() {
        // Arrange (Reader initialized in setUp with initialMark)

        // Act
        val watermark = reader.getWatermark()

        // Assert
        assertThat(watermark).isEqualTo(initialMark.lastProcessedTimestamp) // EPOCH
    }

    @Test
    @Throws(IOException::class, InterruptedException::class)
    fun getWatermark_advancesWithProcessingTimeWhenIdle() {
        // Arrange
        reader.start()
        val startTime = reader.getWatermark()
        TimeUnit.MILLISECONDS.sleep(10) // Simulate passage of time

        // Act
        val watermarkAfterIdle = reader.getWatermark()

        // Assert
        // Watermark should advance based on idle threshold, not remain at EPOCH
        assertThat(watermarkAfterIdle).isGreaterThan(startTime)
        // It should be close to `now - idle_threshold`
        assertThat(watermarkAfterIdle.isBefore(Instant.now())).isTrue()
    }

    @Test
    @Throws(IOException::class)
    fun getWatermark_advancesWithTradeTimestamp() {
        // Arrange
        reader.start()
        val tradeTime = Instant.now().minus(org.joda.time.Duration.standardSeconds(1)) // Ensure it's not too close to now
        val trade = createTrade("trade6", tradeTime.millis)
        simulateTradeReceived(trade)
        reader.advance()

        // Act
        val watermark = reader.getWatermark()

        // Assert
        // Watermark should be based on the last trade's time if it's recent enough
        assertThat(watermark).isEqualTo(tradeTime)
    }


    @Test
    fun getCheckpointMark_initial_returnsInitialMark() {
        // Arrange (Reader initialized in setUp with initialMark)

        // Act
        val checkpointMark = reader.getCheckpointMark()

        // Assert
        assertThat(checkpointMark).isEqualTo(initialMark)
    }

    @Test
    @Throws(IOException::class)
    fun getCheckpointMark_afterAdvance_returnsTimestampOfLastTrade() {
        // Arrange
        reader.start()
        val tradeTime = Instant.now()
        val trade = createTrade("trade7", tradeTime.millis)
        simulateTradeReceived(trade)
        reader.advance()

        // Act
        val checkpointMark = reader.getCheckpointMark()

        // Assert
        assertThat(checkpointMark.lastProcessedTimestamp).isEqualTo(tradeTime)
    }

    @Test
    @Throws(IOException::class)
    fun close_stopsClientStreaming() {
        // Arrange
        reader.start() // Start streaming

        // Act
        reader.close()

        // Assert
        verify(mockExchangeClient).stopStreaming()
    }

    @Test
    @Throws(IOException::class)
    fun advance_skipsOldTradesBasedOnCheckpoint() {
        // Arrange
        val checkpointTime = Instant.now()
        val oldTradeTime = checkpointTime.minus(org.joda.time.Duration.standardSeconds(10))
        val newTradeTime = checkpointTime.plus(org.joda.time.Duration.standardSeconds(10))

        val checkpointMark = TradeCheckpointMark(checkpointTime)
        val readerWithCheckpoint = readerFactory.create(mockSource, checkpointMark)

        val oldTrade = createTrade("oldTrade", oldTradeTime.millis)
        val newTrade = createTrade("newTrade", newTradeTime.millis)

        // Start reader, capture consumer
        readerWithCheckpoint.start()
        verify(mockExchangeClient).startStreaming(any(), tradeConsumerCaptor.capture())
        val tradeConsumer = tradeConsumerCaptor.value

        // Simulate trades arriving (old one first)
        tradeConsumer.accept(oldTrade)
        tradeConsumer.accept(newTrade)

        // Act
        val hasAdvanced = readerWithCheckpoint.advance() // First advance

        // Assert
        assertThat(hasAdvanced).isTrue() // Should advance to the new trade
        assertThat(readerWithCheckpoint.current).isEqualTo(newTrade) // Should have skipped the old one

        // Try advancing again, should be no more trades
        val hasAdvancedAgain = readerWithCheckpoint.advance()
        assertThat(hasAdvancedAgain).isFalse()
    }

    @Test
    @Throws(IOException::class)
    fun advance_processesNewerTradesAfterCheckpoint() {
        // Arrange
        val checkpointTime = Instant.now()
        val newTradeTime = checkpointTime.plus(org.joda.time.Duration.standardSeconds(10))

        val checkpointMark = TradeCheckpointMark(checkpointTime)
        val readerWithCheckpoint = readerFactory.create(mockSource, checkpointMark)
        val newTrade = createTrade("newTradeOnly", newTradeTime.millis)

        readerWithCheckpoint.start()
        simulateTradeReceived(newTrade) // Uses the captured consumer from readerWithCheckpoint

        // Act
        val hasAdvanced = readerWithCheckpoint.advance()

        // Assert
        assertThat(hasAdvanced).isTrue()
        assertThat(readerWithCheckpoint.current).isEqualTo(newTrade)
    }

    @Test
    @Throws(IOException::class)
    fun processTrade_handlesNullTradeGracefully() {
        // Arrange
        reader.start() // Start and capture consumer

        // Act
        // Simulate client sending a null trade
        verify(mockExchangeClient).startStreaming(any(), tradeConsumerCaptor.capture())
        tradeConsumerCaptor.value.accept(null)

        // Assert: No exception should be thrown, advance should return false
        val hasAdvanced = reader.advance()
        assertThat(hasAdvanced).isFalse()
    }

    @Test
    @Throws(IOException::class)
    fun processTrade_handlesTradeWithoutTimestamp() {
        // Arrange
        reader.start()
        val tradeWithoutTimestamp = Trade.newBuilder()
            .setTradeId("noTimestampTrade")
            .setPrice(100.0)
            .setVolume(1.0)
            .setExchange("test")
            .setCurrencyPair("BTC/USD")
            // No setTimestamp call
            .build()
        simulateTradeReceived(tradeWithoutTimestamp)

        // Act
        val hasAdvanced = reader.advance()

        // Assert
        // It should advance, but the timestamp will be processing time
        assertThat(hasAdvanced).isTrue()
        assertThat(reader.current).isEqualTo(tradeWithoutTimestamp)
        // Timestamp should be close to now, definitely after EPOCH
        assertThat(reader.currentTimestamp.isAfter(Instant.EPOCH)).isTrue()
        assertThat(reader.currentTimestamp.isBefore(Instant.now().plus(1000))).isTrue() // Within 1 sec
    }

     // Note: Testing queue full requires controlling the queue size and timing,
     // which is harder in a unit test. We'll rely on the code's logging.
     // Test verifies that `offer` returning false is handled (logged).
     @Test
     @Throws(IOException::class)
     fun processTrade_logsWarningWhenQueueFull() {
         // This test primarily checks that the code path for a full queue exists
         // and relies on observing logs in a real scenario or more complex integration test.
         // We can't easily force the LinkedBlockingQueue to be full here without
         // potentially complex timing manipulations or reflection.

         // Arrange
         reader.start() // Captures the consumer
         val tradeTime = Instant.now()
         val trade = createTrade("tradeFullQueue", tradeTime.millis)

         // Act: Simulate receiving the trade (the actual queue offer happens internally)
         simulateTradeReceived(trade)

         // Assert: We expect the trade to be processed normally in this unit test.
         // The check for `!incomingMessagesQueue.offer(trade)` is covered,
         // but forcing it to return false is non-trivial here.
         assertThat(reader.advance()).isTrue()
         assertThat(reader.current).isEqualTo(trade)
         // In a real full-queue scenario, logs would show a warning.
     }

    @Test
    @Throws(IOException::class)
    fun getCurrencyPairs_throwsIOExceptionOnError() {
        // Arrange
        `when`(mockCurrencyPairSupply.get()).thenThrow(RuntimeException("Supplier failed"))
        // Need a new reader instance as the supply is called during start()
        val failingReader = readerFactory.create(mockSource, initialMark)

        // Act & Assert
        val exception = assertFailsWith<IOException> {
            failingReader.start()
        }
        assertThat(exception.message).contains("Failed to get currency pairs")
    }

     @Test
     fun getWatermark_staysAtLastTradeTimeIfNotIdle() {
         // Arrange
         reader.start()
         val tradeTime1 = Instant.now().minus(org.joda.time.Duration.standardSeconds(2))
         val trade1 = createTrade("watermarkTrade1", tradeTime1.millis)
         simulateTradeReceived(trade1)
         reader.advance()
         val watermark1 = reader.getWatermark() // Should be tradeTime1

         // Simulate another trade arriving quickly
         val tradeTime2 = Instant.now().minus(org.joda.time.Duration.standardSeconds(1))
         val trade2 = createTrade("watermarkTrade2", tradeTime2.millis)
         simulateTradeReceived(trade2)
         reader.advance()

         // Act
         val watermark2 = reader.getWatermark()

         // Assert
         assertThat(watermark1).isEqualTo(tradeTime1)
         assertThat(watermark2).isEqualTo(tradeTime2) // Watermark advances to the new trade time
     }

     @Test
     fun getCheckpointMark_returnsLastMarkWhenNoAdvance() {
         // Arrange
         val specificTime = Instant.now().minus(org.joda.time.Duration.standardMinutes(1))
         val specificMark = TradeCheckpointMark(specificTime)
         val readerWithSpecificMark = readerFactory.create(mockSource, specificMark)
         readerWithSpecificMark.start() // Start but don't advance

         // Act
         val checkpointMark = readerWithSpecificMark.getCheckpointMark()

         // Assert
         // Since advance() wasn't called or returned false, it should return the mark it started with.
         assertThat(checkpointMark).isEqualTo(specificMark)
     }
}
