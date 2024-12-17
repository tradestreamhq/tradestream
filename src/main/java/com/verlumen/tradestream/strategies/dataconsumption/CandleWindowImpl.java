package com.verlumen.tradestream.strategies.dataconsumption;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;
import com.verlumen.tradestream.marketdata.Candle;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

final class CandleWindowImpl implements CandleWindow {
    private final List<Candle> candles = Collections.synchronizedList(new ArrayList<>());
    private final Duration timeframe;

    @Inject
    CandleWindowImpl(Duration timeframe) {
        this.timeframe = timeframe;
    }

    void addCandle(Candle candle) {
        candles.add(candle);
    }

    ImmutableList<Candle> getCandles(int windowSize) {
        synchronized (candles) {
            int fromIndex = Math.max(0, candles.size() - windowSize);
            return ImmutableList.copyOf(candles.subList(fromIndex, candles.size()));
        }
    }
}
