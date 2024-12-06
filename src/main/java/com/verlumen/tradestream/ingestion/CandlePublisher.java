package com.verlumen.tradestream.ingestion;

import com.verlumen.tradestream.marketdata.Candle;

import java.time.Duration;

interface CandlePublisher {
    void publishCandle(Candle candle);

    void close();

    interface Factory {
        CandlePublisher create(String topic);
    }
}
