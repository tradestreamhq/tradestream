package com.verlumen.tradestream.signals;

import java.io.Serializable;

public interface TradeSignalPublisher extends Serializable {
    void publish(TradeSignal signal);

    void close();

        /**
     * Factory interface for creating TradeSignalPublisher instances.
     */
    interface Factory {
        TradeSignalPublisher create(String topic);
    }
}
