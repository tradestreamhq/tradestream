package com.verlumen.tradestream.ingestion;

import com.google.common.flogger.FluentLogger;
import com.google.inject.assistedinject.Assisted;
import com.google.inject.Inject;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.marketdata.Trade;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import java.time.Duration;

final class TradePublisherImpl implements TradePublisher {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    private final KafkaProducer<String, byte[]> kafkaProducer;
    private final String topic;

    @Inject
    TradePublisherImpl(
        KafkaProducer<String, byte[]> kafkaProducer,
        @Assisted String topic
    ) {
        logger.atInfo().log("Initializing TradePublisher for topic: %s", topic);
        this.topic = topic;
        this.kafkaProducer = kafkaProducer;
        logger.atInfo().log("TradePublisher initialization complete");
    }

    public void publishTrade(Trade trade) {
        logger.atInfo().log("Publishing trade for %s to topic %s. Timestamp=%s, Open=%f, High=%f, Low=%f, Close=%f, Volume=%f", 
            trade.getCurrencyPair(), 
            topic,
            Timestamps.toString(trade.getTimestamp()),
            trade.getOpen(),
            trade.getHigh(),
            trade.getLow(),
            trade.getClose(),
            trade.getVolume());

        byte[] tradeBytes = trade.toByteArray();
        logger.atFine().log("Serialized trade data size: %d bytes", tradeBytes.length);

        ProducerRecord<String, byte[]> record = new ProducerRecord<>(
            topic,
            trade.getCurrencyPair(),
            tradeBytes
        );

        kafkaProducer.send(record, (metadata, exception) -> {
            if (exception != null) {
                logger.atSevere().withCause(exception)
                    .log("Failed to publish trade for %s to topic %s", 
                        trade.getCurrencyPair(), topic);
            } else {
                logger.atInfo().log("Successfully published trade: topic=%s, partition=%d, offset=%d, timestamp=%d",
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
