package com.verlumen.tradestream.strategies;

import com.google.inject.Inject;
import com.verlumen.tradestream.marketdata.Candle;
import org.ta4j.core.Strategy;

/**
 * Core implementation of the Strategy Engine that coordinates strategy optimization,
 * candlestick processing, and trade signal generation.
 */
final class StrategyEngineImpl implements StrategyEngine {
    @Inject
    StrategyEngineImpl() {}

    @Override
    public synchronized void handleCandle(Candle candle) {
        throw new UnsupportedOperationException();
    }

    @Override
    public synchronized void optimizeStrategy() {
        throw new UnsupportedOperationException();
    }

    @Override
    public Strategy getCurrentStrategy() {
        throw new UnsupportedOperationException();
    }
}
