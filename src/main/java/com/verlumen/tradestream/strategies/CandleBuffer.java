package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.marketdata.Candle;
import org.ta4j.core.BarSeries;

interface CandleBuffer {
    void add(Candle candle);
    ImmutableList<Candle> getCandles();
    BarSeries toBarSeries();
}
