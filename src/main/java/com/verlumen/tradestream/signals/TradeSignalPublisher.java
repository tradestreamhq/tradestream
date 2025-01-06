package com.verlumen.tradestream.signals;

interface TradeSignalPublisher {
    void publish(TradeSignal signal);

    void close();

        /**
     * Factory interface for creating TradeSignalPublisher instances.
     */
    interface Factory {
        TradeSignalPublisher create(String topic);
    }
}
