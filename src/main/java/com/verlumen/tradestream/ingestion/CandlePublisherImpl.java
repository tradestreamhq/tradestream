package com.verlumen.tradestream.ingestion;

import com.google.common.flogger.FluentLogger;
import com.google.inject.assistedinject.Assisted;
import com.google.inject.Inject;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.marketdata.Candle;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import java.time.Duration;

final class CandlePublisherImpl implements CandlePublisher {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    private final KafkaProducer<String, byte[]> kafkaProducer;
    private final String topic;

    @Inject
    CandlePublisherImpl(
        KafkaProducer<String, byte[]> kafkaProducer,
        @Assisted String topic
    ) {
        logger.atInfo().log("Initializing CandlePublisher for topic: %s", topic);
        this.topic = topic;
        this.kafkaProducer = kafkaProducer;
        logger.atInfo().log("CandlePublisher initialization complete");
    }

    public void publishCandle(Candle candle) {
        logger.atInfo().log("Publishing candle for %s to topic %s. Timestamp=%d, Open=%f, High=%f, Low=%f, Close=%f, Volume=%f", 
            candle.getCurrencyPair(), 
            topic,
            Timestamps.toString(candle.getTimestamp()),
            candle.getOpen(),
            candle.getHigh(),
            candle.getLow(),
            candle.getClose(),
            candle.getVolume());

        byte[] candleBytes = candle.toByteArray();
        logger.atFine().log("Serialized candle data size: %d bytes", candleBytes.length);

        ProducerRecord<String, byte[]> record = new ProducerRecord<>(
            topic,
            candle.getCurrencyPair(),
            candleBytes
        );

        kafkaProducer.send(record, (metadata, exception) -> {
            if (exception != null) {
                logger.atSevere().withCause(exception)
                    .log("Failed to publish candle for %s to topic %s", 
                        candle.getCurrencyPair(), topic);
            } else {
                logger.atInfo().log("Successfully published candle: topic=%s, partition=%d, offset=%d, timestamp=%d",
                    metadata.topic(), 
                    metadata.partition(), 
                    metadata.offset(),
                    metadata.timestamp());
            }
        });
    }

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
