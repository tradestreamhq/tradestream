package com.verlumen.tradestream.marketdata;

import java.time.Duration;

public interface TradePublisher {
    void publishTrade(Trade trade);

    void close();

    interface Factory {
        TradePublisher create(String topic);
    }
}
