package com.verlumen.tradestream.strategies;

import static com.google.common.base.Preconditions.checkNotNull;
import static com.google.common.base.Preconditions.checkState;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Inject;
import com.verlumen.tradestream.marketdata.Candle;
import java.time.Duration;
import java.util.Collections;
import java.util.Properties;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;
import javax.inject.Named;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.errors.WakeupException;
import org.apache.kafka.common.serialization.ByteArrayDeserializer;

/**
 * Consumes candle data from a Kafka topic using the Kafka Consumer API.
 * Supports graceful shutdown and error handling.
 */
final class MarketDataConsumerImpl implements MarketDataConsumer {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    private static final Duration POLL_TIMEOUT = Duration.ofMillis(100);

    private final Properties kafkaProperties;
    private final String topic;
    private final ExecutorService executorService;
    private final AtomicBoolean running;
    private volatile KafkaConsumer<byte[], byte[]> consumer;

    @Inject
    MarketDataConsumerImpl(
            @Named("kafka.bootstrap.servers") String bootstrapServers,
            @Named("kafka.group.id") String groupId,
            @Named("kafka.topic") String topic) {
        this.topic = checkNotNull(topic);
        this.kafkaProperties = createConsumerProperties(
            checkNotNull(bootstrapServers),
            checkNotNull(groupId)
        );
        this.executorService = Executors.newSingleThreadExecutor();
        this.running = new AtomicBoolean(false);
    }

    @Override
    public synchronized void startConsuming(Consumer<Candle> handler) {
        checkNotNull(handler, "Handler cannot be null");
        checkState(!running.get(), "Consumer is already running");

        try {
            consumer = new KafkaConsumer<>(kafkaProperties);
            consumer.subscribe(Collections.singletonList(topic));
            running.set(true);

            // Start consumption in a separate thread
            executorService.submit(() -> consumeMessages(handler));
            logger.atInfo().log("Started consuming from topic: %s", topic);

        } catch (Exception e) {
            running.set(false);
            if (consumer != null) {
                consumer.close();
            }
            throw new RuntimeException("Failed to start consumer", e);
        }
    }

    @Override
    public synchronized void stopConsuming() {
        if (running.compareAndSet(true, false)) {
            try {
                // Signal the consumer to stop
                if (consumer != null) {
                    consumer.wakeup();
                }
                
                // Wait for consumption to complete
                executorService.shutdown();
                if (!executorService.awaitTermination(POLL_TIMEOUT)) {
                    executorService.shutdownNow();
                }

                // Clean up consumer
                if (consumer != null) {
                    consumer.close();
                    consumer = null;
                }

                logger.atInfo().log("Stopped consuming from topic: %s", topic);

            } catch (Exception e) {
                logger.atWarning().withCause(e)
                    .log("Error during consumer shutdown");
                executorService.shutdownNow();
                throw new RuntimeException("Failed to stop consumer", e);
            }
        }
    }

    private void consumeMessages(Consumer<Candle> handler) {
        try {
            while (running.get()) {
                consumer.poll(POLL_TIMEOUT).forEach(record -> {
                    try {
                        Candle candle = Candle.parseFrom(record.value());
                        handler.accept(candle);
                    } catch (Exception e) {
                        logger.atWarning()
                            .withCause(e)
                            .log("Error processing message from partition %d offset %d",
                                record.partition(), record.offset());
                    }
                });
            }
        } catch (WakeupException e) {
            // Ignore exception if stopping
            if (running.get()) {
                throw e;
            }
        } catch (Exception e) {
            logger.atSevere()
                .withCause(e)
                .log("Error consuming messages from topic %s", topic);
            throw new RuntimeException("Consumer loop failed", e);
        } finally {
            try {
                consumer.commitSync();
            } catch (Exception e) {
                logger.atWarning()
                    .withCause(e)
                    .log("Error committing final offsets");
            }
        }
    }

    private static Properties createConsumerProperties(
            String bootstrapServers, String groupId) {
        Properties props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        props.put(ConsumerConfig.GROUP_ID_CONFIG, groupId);
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG,
                 ByteArrayDeserializer.class.getName());
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, 
                 ByteArrayDeserializer.class.getName());
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "latest");
        props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, "false");
        return props;
    }
}
