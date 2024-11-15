package com.verlumen.tradestream.ingestion;

import marketdata.Marketdata.Candle;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import java.time.Duration;

interface CandlePublisher {
    void publishCandle(Candle candle) {}

    void close() {}
}
