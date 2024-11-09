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

        // Use the dependency injection constructor
        realTimeDataIngestion = new RealTimeDataIngestion(
                mockStreamingExchange,
                mockStreamingMarketDataService,
                mockKafkaProducer,
                ImmutableList.of("BTC/USD"),
                "test-topic"
        );
    }

    /** Tests that onCandle sends the candle to Kafka. */
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
        // Since internal state is private, verify that onCandle is called only once
        // Here, we can use a spy or mock to verify interactions
        KafkaProducer<String, byte[]> spyKafkaProducer = spy(mockKafkaProducer);
        RealTimeDataIngestion spyIngestion = new RealTimeDataIngestion(
                mockStreamingExchange,
                mockStreamingMarketDataService,
                spyKafkaProducer,
                ImmutableList.of("BTC/USD"),
                "test-topic"
        );

        // Act
        spyIngestion.onTrade(testTrade);
        spyIngestion.onTrade(testTrade); // Duplicate trade

        // Assert
        verify(spyKafkaProducer, times(1)).send(any(), any());
    }

    /** Tests that start connects to exchange and subscribes to trades. */
    @Test
    public void start_connectsAndSubscribes() {
        // Arrange
        when(mockStreamingMarketDataService.getTrades(any()))
                .thenReturn(io.reactivex.rxjava3.core.Observable.never());

        // Act
        realTimeDataIngestion.start();

        // Assert
        verify(mockStreamingExchange).connect();
        verify(mockStreamingMarketDataService, times(1)).getTrades(any());
    }

    /** Tests that shutdown closes Kafka producer and disconnects exchange. */
    @Test
    public void shutdown_closesResources() {
        // Act
        realTimeDataIngestion.shutdown();

        // Assert
        verify(mockKafkaProducer).close(any(Duration.class));
        verify(mockStreamingExchange).disconnect();
    }

    // Additional tests should focus on observable behaviors via public methods
}
