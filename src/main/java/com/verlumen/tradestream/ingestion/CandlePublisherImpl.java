package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import marketdata.Marketdata.Candle;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import java.time.Duration;

final class CandlePublisherImpl implements CandlePublisher {
    private final KafkaProducer<String, byte[]> kafkaProducer;

    @Inject
    CandlePublisherImpl(KafkaProducer<String, byte[]> kafkaProducer) {
        this.kafkaProducer = kafkaProducer;
    }

    public void publishCandle(PublishParams params) {
        ProducerRecord<String, byte[]> record = new ProducerRecord<>(
            params.topic(),
            params.candle().getCurrencyPair(),
            params.candle().toByteArray()
        );

        kafkaProducer.send(record, (metadata, exception) -> {
            if (exception != null) {
                exception.printStackTrace();
            }
        });
    }

    public void close() {
        kafkaProducer.close(Duration.ofSeconds(5));
    }
}
