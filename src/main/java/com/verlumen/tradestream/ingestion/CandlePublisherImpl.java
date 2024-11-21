package com.verlumen.tradestream.ingestion;

import com.google.inject.assistedinject.Assisted;
import com.google.inject.Inject;
import com.verlumen.tradestream.marketdata.Candle;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import java.time.Duration;

final class CandlePublisherImpl implements CandlePublisher {
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
        ProducerRecord<String, byte[]> record = new ProducerRecord<>(
            topic,
            candle.getCurrencyPair(),
            candle.toByteArray()
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
