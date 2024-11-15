package com.verlumen.tradestream.ingestion;

import marketdata.Marketdata.Candle;

interface CandlePublisher {
    public void publishCandle(Candle candle);
    public void close();

    interface Factory {
        CandlePublisher create();
    }
}
