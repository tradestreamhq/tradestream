package com.verlumen.tradestream.strategies;

import com.verlumen.tradestream.signals.TradeSignal;

interface TradeSignalPublisher {
    void publish(TradeSignal signal);
}
