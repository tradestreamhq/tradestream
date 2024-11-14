package com.verlumen.tradestream.ingestion;

import marketdata.Marketdata.Candle;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import java.time.Duration;

class CandlePublisher {
    private final KafkaProducer<String, byte[]> kafkaProducer;
    private final String topic;

    CandlePublisher(KafkaProducer<String, byte[]> kafkaProducer, String topic) {
        this.kafkaProducer = kafkaProducer;
        this.topic = topic;
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
