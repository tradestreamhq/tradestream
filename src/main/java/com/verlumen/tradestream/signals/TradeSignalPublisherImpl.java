package com.verlumen.tradestream.signals;

import com.google.common.flogger.FluentLogger;
import com.google.inject.assistedinject.Assisted;
import com.google.inject.Inject;
import com.google.protobuf.util.Timestamps;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import java.time.Duration;

/**
 * Kafka-based implementation of TradeSignalPublisher that publishes trade signals to a specified topic.
 */
final class TradeSignalPublisherImpl implements TradeSignalPublisher {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    private final KafkaProducerFactory kafkaProducerFactory;
    private final String topic;

    @Inject
    TradeSignalPublisherImpl(
        KafkaProducerFactory kafkaProducerFactory,
        @Assisted String topic
    ) {
        logger.atInfo().log("Initializing TradeSignalPublisher for topic: %s", topic);
        this.kafkaProducer = kafkaProducer;
        this.topic = topic;
        logger.atInfo().log("TradeSignalPublisher initialization complete");
    }

    @Override
    public void publish(TradeSignal signal) {
        logger.atInfo().log("Publishing trade signal to topic %s. Type=%s, Timestamp=%s, Price=%f", 
            topic,
            signal.getType(),
            Timestamps.toString(Timestamps.fromMillis(signal.getTimestamp())),
            signal.getPrice());

        byte[] signalBytes = signal.toByteArray();
        logger.atFine().log("Serialized signal data size: %d bytes", signalBytes.length);

        // Use the strategy type as the key for partitioning
        String key = signal.getStrategy().getType().name();

        ProducerRecord<String, byte[]> record = new ProducerRecord<>(
            topic,
            key,
            signalBytes
        );

        kafkaProducer.send(record, (metadata, exception) -> {
            if (exception != null) {
                logger.atSevere().withCause(exception)
                    .log("Failed to publish trade signal for %s to topic %s", 
                        signal.getStrategy().getType(), topic);
            } else {
                logger.atInfo().log("Successfully published signal: topic=%s, partition=%d, offset=%d, timestamp=%d",
                    metadata.topic(), 
                    metadata.partition(), 
                    metadata.offset(),
                    metadata.timestamp());
            }
        });
    }

    @Override
    public void close() {
        logger.atInfo().log("Initiating Kafka producer shutdown");
        try {
            logger.atInfo().log("Flushing any pending messages...");
            kafkaProducer.flush();
            logger.atInfo().log("Starting graceful shutdown with 5 second timeout");
            kafkaProducer.close(Duration.ofSeconds(5));
            logger.atInfo().log("Kafka producer closed successfully");
        } catch (Exception e) {
            logger.atSevere().withCause(e).log("Error during Kafka producer shutdown");
            throw e;
        }
    }
}
