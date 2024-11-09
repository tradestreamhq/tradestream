package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.InvalidProtocolBufferException;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingMarketDataService;
import io.reactivex.rxjava3.core.Completable;
import io.reactivex.rxjava3.disposables.Disposable;
import marketdata.Marketdata.Candle;
import marketdata.Marketdata.Trade;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.junit.*;
import org.junit.runner.RunWith;
import org.mockito.*;
import com.google.testing.junit.testparameterinjector.TestParameterInjector;
import com.google.testing.junit.testparameterinjector.TestParameter;

import java.time.Duration;
import java.util.Properties;
import java.util.UUID;

@RunWith(TestParameterInjector.class)
public class RealTimeDataIngestionTest {

    @Mock private StreamingExchange mockStreamingExchange;
    @Mock private StreamingMarketDataService mockStreamingMarketDataService;
    @Mock private KafkaProducer<String, byte[]> mockKafkaProducer;
    @Mock private Disposable mockDisposable;

    @Captor private ArgumentCaptor<ProducerRecord<String, byte[]>> recordCaptor;

    private RealTimeDataIngestion realTimeDataIngestion;

    @Before
    public void setUp() throws Exception {
        MockitoAnnotations.openMocks(this);

        when(mockStreamingExchange.getStreamingMarketDataService()).thenReturn(mockStreamingMarketDataService);
        when(mockStreamingExchange.connect()).thenReturn(Completable.complete());
        when(mockStreamingExchange.disconnect()).thenReturn(Completable.complete());
        when(mockStreamingMarketDataService.getTrades(any()))
                .thenReturn(io.reactivex.rxjava3.core.Observable.never());

        Properties kafkaProps = new Properties();
        realTimeDataIngestion = new RealTimeDataIngestion(
                "com.example.ExchangeClassName",
                ImmutableList.of("BTC/USD"),
                kafkaProps,
                "test-topic"
        );

        // Inject mocks
        realTimeDataIngestion.streamingExchange = mockStreamingExchange;
        realTimeDataIngestion.streamingMarketDataService = mockStreamingMarketDataService;
        realTimeDataIngestion.kafkaProducer = mockKafkaProducer;
    }

    /** Tests getMinuteTimestamp with various timestamps. */
    @Test
    public void getMinuteTimestamp_returnsCorrectTimestamp(
            @TestParameter MinuteTimestampTestCase testCase) {
        // Arrange
        long timestamp = testCase.input;

        // Act
        long minuteTimestamp = realTimeDataIngestion.getMinuteTimestamp(timestamp);

        // Assert
        assertEquals(testCase.expected, minuteTimestamp);
    }

    /** Test cases for getMinuteTimestamp. */
    private enum MinuteTimestampTestCase {
        ZERO(0L, 0L),
        EXACT_MINUTE(1622548800000L, 1622548800000L),
        MID_MINUTE(1622548805123L, 1622548800000L),
        NEGATIVE(-1L, -60000L);

        public final long input;
        public final long expected;

        MinuteTimestampTestCase(long input, long expected) {
            this.input = input;
            this.expected = expected;
        }
    }

    /** Tests getCandleKey returns the correct key format. */
    @Test
    public void getCandleKey_returnsCorrectKey() {
        // Arrange
        String currencyPair = "BTC/USD";
        long timestamp = 1622548800000L;

        // Act
        String candleKey = realTimeDataIngestion.getCandleKey(currencyPair, timestamp);

        // Assert
        assertEquals("BTC/USD:1622548800000", candleKey);
    }

    /** Tests onCandle sends the candle to Kafka. */
    @Test
    public void onCandle_sendsCandleToKafka() throws Exception {
        // Arrange
        Candle testCandle = Candle.newBuilder()
                .setTimestamp(1622548800000L)
                .setCurrencyPair("BTC/USD")
                .setOpen(50000.0)
                .setHigh(51000.0)
                .setLow(49000.0)
                .setClose(50500.0)
                .setVolume(10.0)
                .build();

        // Act
        realTimeDataIngestion.onCandle(testCandle);

        // Assert
        verify(mockKafkaProducer).send(recordCaptor.capture(), any());
        ProducerRecord<String, byte[]> sentRecord = recordCaptor.getValue();
        assertEquals("test-topic", sentRecord.topic());
        assertEquals("BTC/USD", sentRecord.key());
        assertArrayEquals(testCandle.toByteArray(), sentRecord.value());
    }

    /** Tests that duplicate trades are ignored to ensure idempotency. */
    @Test
    public void onTrade_duplicateTrade_isIgnored() {
        // Arrange
        long timestamp = System.currentTimeMillis();
        Trade testTrade = Trade.newBuilder()
                .setTimestamp(timestamp)
                .setExchange("TestExchange")
                .setCurrencyPair("BTC/USD")
                .setPrice(50000.0)
                .setVolume(1.0)
                .setTradeId("trade1")
                .build();

        // Act
        realTimeDataIngestion.onTrade(testTrade);
        realTimeDataIngestion.onTrade(testTrade); // Duplicate trade

        // Assert
        int processedTradesSize = realTimeDataIngestion.processedTrades.size();
        assertEquals(1, processedTradesSize);
    }

    /** Tests that a trade with null tradeId generates a UUID. */
    @Test
    public void onTrade_withNullTradeId_generatesRandomId() {
        // Arrange
        long timestamp = System.currentTimeMillis();
        Trade testTrade = Trade.newBuilder()
                .setTimestamp(timestamp)
                .setExchange("TestExchange")
                .setCurrencyPair("BTC/USD")
                .setPrice(50000.0)
                .setVolume(1.0)
                .build(); // No tradeId

        // Act
        realTimeDataIngestion.onTrade(testTrade);

        // Assert
        assertEquals(1, realTimeDataIngestion.processedTrades.size());
    }

    /** Tests that CandleBuilder correctly aggregates multiple trades. */
    @Test
    public void candleBuilder_aggregatesTradesCorrectly() {
        // Arrange
        String currencyPair = "BTC/USD";
        long timestamp = realTimeDataIngestion.getMinuteTimestamp(System.currentTimeMillis());
        RealTimeDataIngestion.CandleBuilder candleBuilder =
                realTimeDataIngestion.new CandleBuilder(currencyPair, timestamp);

        Trade trade1 = Trade.newBuilder()
                .setTimestamp(timestamp)
                .setExchange("TestExchange")
                .setCurrencyPair(currencyPair)
                .setPrice(50000.0)
                .setVolume(1.0)
                .setTradeId("trade1")
                .build();

        Trade trade2 = Trade.newBuilder()
                .setTimestamp(timestamp + 1000)
                .setExchange("TestExchange")
                .setCurrencyPair(currencyPair)
                .setPrice(51000.0)
                .setVolume(2.0)
                .setTradeId("trade2")
                .build();

        Trade trade3 = Trade.newBuilder()
                .setTimestamp(timestamp + 2000)
                .setExchange("TestExchange")
                .setCurrencyPair(currencyPair)
                .setPrice(49000.0)
                .setVolume(1.5)
                .setTradeId("trade3")
                .build();

        // Act
        candleBuilder.addTrade(trade1);
        candleBuilder.addTrade(trade2);
        candleBuilder.addTrade(trade3);

        // Assert
        Candle candle = candleBuilder.buildCandle();
        assertThat(candle.getOpen()).isEqualTo(50000.0);
        assertThat(candle.getHigh()).isEqualTo(51000.0);
        assertThat(candle.getLow()).isEqualTo(49000.0);
        assertThat(candle.getClose()).isEqualTo(49000.0);
        assertThat(candle.getVolume()).isEqualTo(4.5);
    }

    /** Tests handleThinlyTradedMarkets generates empty candles when needed. */
    @Test
    public void handleThinlyTradedMarkets_generatesEmptyCandles() {
        // Arrange
        realTimeDataIngestion.currencyPairs = ImmutableList.of("BTC/USD");
        realTimeDataIngestion.candleBuilders.clear();

        // Act
        realTimeDataIngestion.handleThinlyTradedMarkets();

        // Assert
        int candleBuildersSize = realTimeDataIngestion.candleBuilders.size();
        assertThat(candleBuildersSize).isEqualTo(1);
    }

    /** Tests getLastKnownPrice returns NaN when not implemented. */
    @Test
    public void getLastKnownPrice_returnsNaN() {
        // Arrange
        String currencyPair = "BTC/USD";

        // Act
        double lastPrice = realTimeDataIngestion.getLastKnownPrice(currencyPair);

        // Assert
        assertThat(lastPrice).isNaN();
    }

    /** Tests shutdown closes Kafka producer and disconnects exchange. */
    @Test
    public void shutdown_closesResources() {
        // Act
        realTimeDataIngestion.shutdown();

        // Assert
        verify(mockKafkaProducer).close(any(Duration.class));
        verify(mockStreamingExchange).disconnect();
    }

    /** Tests start connects to exchange and subscribes to trades. */
    @Test
    public void start_connectsAndSubscribes() {
        // Arrange
        when(mockStreamingMarketDataService.getTrades(any()))
                .thenReturn(io.reactivex.rxjava3.core.Observable.never());

        // Act
        realTimeDataIngestion.start();

        // Assert
        verify(mockStreamingExchange).connect();
        verify(mockStreamingMarketDataService).getTrades(any());
    }

    /** Tests that trades with invalid data are handled gracefully. */
    @Test
    public void onTrade_withInvalidData_handlesGracefully() {
        // Arrange
        Trade invalidTrade = Trade.newBuilder().build(); // Missing required fields

        // Act
        realTimeDataIngestion.onTrade(invalidTrade);

        // Assert
        // No exception should be thrown
    }
}
