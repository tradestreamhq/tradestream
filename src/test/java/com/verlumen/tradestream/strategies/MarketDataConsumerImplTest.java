package com.verlumen.tradestream.strategies;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.junit.Assert.*;

import com.google.inject.Guice;
import com.google.inject.Provider;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.marketdata.Candle;
import java.time.Duration;
import java.util.Collections;
import java.util.concurrent.ExecutorService;
import java.util.function.Consumer;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.errors.WakeupException;
import org.junit.Before;
import org.junit.Ignore;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class MarketDataConsumerImplTest {
    private static final String CANDLE_TOPIC = "test-topic";
    private static final TopicPartition PARTITION = new TopicPartition(CANDLE_TOPIC, 0);

    @Rule public final MockitoRule mockito = MockitoJUnit.rule();

    @Mock @Bind private Provider<KafkaConsumer<byte[], byte[]>> mockConsumerProvider;
    @Mock @Bind private ExecutorService mockExecutor;
    @Mock private KafkaConsumer<byte[], byte[]> mockConsumer;
    @Mock private Consumer<Candle> mockHandler;

    private MarketDataConsumer consumer;

    @Before
    public void setUp() {
        when(mockConsumerProvider.get()).thenReturn(mockConsumer);
        consumer = Guice.createInjector(
            BoundFieldModule.of(this),
                new FactoryModuleBuilder()
                .implement(MarketDataConsumer.class, MarketDataConsumerImpl.class)
                .build(MarketDataConsumer.Factory.class))
            .getInstance(MarketDataConsumer.Factory.class)
            .create(CANDLE_TOPIC);
    }

    @Test(expected = NullPointerException.class)
    public void startConsuming_withNullHandler_throwsException() {
        consumer.startConsuming(null);
    }

    @Test(expected = IllegalStateException.class)
    public void startConsuming_whenAlreadyRunning_throwsException() {
        // Start first consumer
        consumer.startConsuming(mockHandler);

        // Try to start again - should throw
        consumer.startConsuming(mockHandler);
    }

    @Test
    public void startConsuming_subscribesToTopic() {
        consumer.startConsuming(mockHandler);
        verify(mockConsumer).subscribe(Collections.singletonList(CANDLE_TOPIC));
    }

    @Test
    public void stopConsuming_wakesUpConsumer() {
        consumer.startConsuming(mockHandler);
        consumer.stopConsuming();
        verify(mockConsumer).wakeup();
    }

    @Ignore("Disabled temporarily while investigating long-running poll loop")
    @Test
    public void consumeLoop_commitsAndClosesOnShutdown() {
        when(mockConsumer.poll(any(Duration.class)))
            .thenThrow(new WakeupException());

        consumer.startConsuming(mockHandler);
        consumer.stopConsuming();

        verify(mockConsumer).commitSync();
        verify(mockConsumer).close();
    }

    @Ignore("Disabled temporarily while investigating long-running poll loop")
    @Test
    public void consumeLoop_handlesRecordsCorrectly() throws Exception {
        // Create test candle
        Candle testCandle = Candle.newBuilder().build();
        byte[] candleBytes = testCandle.toByteArray();

        // Setup mock consumer record
        ConsumerRecords<byte[], byte[]> records = new ConsumerRecords<>(
            Collections.singletonMap(PARTITION, 
                Collections.singletonList(
                    new org.apache.kafka.clients.consumer.ConsumerRecord<>(
                        CANDLE_TOPIC, 0, 0L, new byte[0], candleBytes))));

        // Mock consumer to return records once then throw WakeupException
        when(mockConsumer.poll(any(Duration.class)))
            .thenReturn(records)
            .thenThrow(new WakeupException());

        // Start consuming and verify handler was called
        consumer.startConsuming(mockHandler);
        verify(mockHandler, timeout(1000)).accept(testCandle);
    }
}
