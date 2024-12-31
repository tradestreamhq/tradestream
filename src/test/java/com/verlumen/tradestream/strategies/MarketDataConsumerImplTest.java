package com.verlumen.tradestream.strategies;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.timeout;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.google.inject.Guice;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.marketdata.Candle;
import java.time.Duration;
import java.time.Instant;
import java.util.Collections;
import java.util.function.Consumer;
import javax.inject.Named;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.errors.WakeupException;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class MarketDataConsumerImplTest {
    private static final String TOPIC = "test-topic";
    private static final TopicPartition PARTITION = 
        new TopicPartition(TOPIC, 0);

    @Rule public MockitoRule mockito = MockitoJUnit.rule();

    @Bind @Named("kafka.bootstrap.servers")
    private final String bootstrapServers = "localhost:9092";

    @Bind @Named("kafka.group.id")
    private final String groupId = "test-group";

    @Bind @Named("kafka.topic")
    private final String topic = TOPIC;

    @Mock private KafkaConsumer<byte[], byte[]> mockConsumer;
    @Mock private Consumer<Candle> mockHandler;

    private MarketDataConsumerImpl consumer;

    @Before
    public void setUp() {
        consumer = new MarketDataConsumerImpl(bootstrapServers, groupId, topic);
    }

    @Test
    public void startConsuming_withNullHandler_throwsException() {
        assertThrows(NullPointerException.class,
            () -> consumer.startConsuming(null));
    }

    @Test
    public void startConsuming_whenAlreadyRunning_throwsException() {
        // Start first consumer
        consumer.startConsuming(mockHandler);

        // Try to start again
        assertThrows(IllegalStateException.class,
            () -> consumer.startConsuming(mockHandler));

        // Cleanup
        consumer.stopConsuming();
    }

    @Test
    public void consumeMessages_handlesRecordsCorrectly() throws Exception {
        // Create test candle
        Candle testCandle = createTestCandle(100.0);
        byte[] candleBytes = testCandle.toByteArray();

        // Setup mock consumer record
        ConsumerRecord<byte[], byte[]> record = 
            new ConsumerRecord<>(TOPIC, 0, 0L, new byte[0], candleBytes);
        ConsumerRecords<byte[], byte[]> records = new ConsumerRecords<>(
            Collections.singletonMap(PARTITION, Collections.singletonList(record)));

        // Mock consumer behavior
        when(mockConsumer.poll(any(Duration.class)))
            .thenReturn(records)
            .thenThrow(WakeupException.class);

        // Start consuming
        consumer.startConsuming(mockHandler);

        // Verify handler was called with correct candle
        verify(mockHandler, timeout(1000)).accept(testCandle);

        // Cleanup
        consumer.stopConsuming();
    }

    @Test
    public void consumeMessages_handlesParsingErrors() throws Exception {
        // Setup invalid record
        ConsumerRecord<byte[], byte[]> record = 
            new ConsumerRecord<>(TOPIC, 0, 0L, new byte[0], new byte[]{1,2,3});
        ConsumerRecords<byte[], byte[]> records = new ConsumerRecords<>(
            Collections.singletonMap(PARTITION, Collections.singletonList(record)));

        // Mock consumer behavior
        when(mockConsumer.poll(any(Duration.class)))
            .thenReturn(records)
            .thenThrow(WakeupException.class);

        // Start consuming - should not throw exception
        consumer.startConsuming(mockHandler);

        // Verify handler was not called
        verify(mockHandler, timeout(1000).times(0)).accept(any());

        // Cleanup
        consumer.stopConsuming();
    }

    @Test
    public void stopConsuming_performsCleanShutdown() {
        // Start consuming
        consumer.startConsuming(mockHandler);

        // Stop consuming
        consumer.stopConsuming();

        // Verify consumer is stopped
        assertThrows(IllegalStateException.class,
            () -> consumer.startConsuming(mockHandler));
    }

    private Candle createTestCandle(double price) {
        return Candle.newBuilder()
            .setTimestamp(Instant.now().toEpochMilli())
            .setOpen(price)
            .setHigh(price)
            .setLow(price)
            .setClose(price)
            .setVolume(1000)
            .build();
    }
}
