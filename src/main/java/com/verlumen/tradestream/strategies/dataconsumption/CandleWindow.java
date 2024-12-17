package com.verlumen.tradestream.strategies.dataconsumption;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.marketdata.Candle;

public interface CandleWindow {
    void addCandle(Candle candle);

    ImmutableList<Candle> getCandles(int windowSize);
}
