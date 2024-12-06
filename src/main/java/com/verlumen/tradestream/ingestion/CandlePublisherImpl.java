package com.verlumen.tradestream.ingestion;

import com.google.common.flogger.FluentLogger;
import com.google.inject.assistedinject.Assisted;
import com.google.inject.Inject;
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
        this.topic = topic;
        this.kafkaProducer = kafkaProducer;
    }

    public void publishCandle(Candle candle) {
        logger.atInfo().log("Publishing candle for %s to topic %s", 
            candle.getCurrencyPair(), topic);
        ProducerRecord<String, byte[]> record = new ProducerRecord<>(
            topic,
            candle.getCurrencyPair(),
            candle.toByteArray()
        );

        kafkaProducer.send(record, (metadata, exception) -> {
            if (exception != null) {
                logger.atSevere().withCause(exception)
                    .log("Failed to publish candle for %s", candle.getCurrencyPair());
            } else {
                logger.atFine().log("Successfully published candle: topic=%s, partition=%d, offset=%d",
                    metadata.topic(), metadata.partition(), metadata.offset());
            }
        });
    }

    public void close() {
        logger.atInfo().log("Closing Kafka producer");
        kafkaProducer.close(Duration.ofSeconds(5));
        logger.atInfo().log("Kafka producer closed successfully");
    }
}
