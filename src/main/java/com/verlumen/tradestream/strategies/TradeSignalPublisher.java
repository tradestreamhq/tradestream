package com.verlumen.tradestream.strategies;

import com.verlumen.tradestream.signals;

interface TradeSignalPublisher {
    void publish(TradeSignal signal);
}
