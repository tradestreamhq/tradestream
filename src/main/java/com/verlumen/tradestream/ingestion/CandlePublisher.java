package com.verlumen.tradestream.ingestion;

import marketdata.Marketdata.Candle;

import java.time.Duration;

interface CandlePublisher {
    void publishCandle(PublishParams params);

    void close();

    @AutoValue
    abstract class PublishParams {
        static PublishParams create(String topic, Candle candle) {
            return new AutoValue_CandlePublisher_PublishParams(topic, candle);
        }

        abstract String topic();
        abstract Candle candle();
    }
}
