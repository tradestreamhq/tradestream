package com.verlumen.tradestream.ingestion;

import com.verlumen.tradestream.marketdata.Trade;

import java.time.Duration;

public interface TradePublisher {
    void publishTrade(Trade trade);

    void close();

    interface Factory {
        TradePublisher create(String topic);
    }
}
