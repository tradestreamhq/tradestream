package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.time.Timestamps;
import java.time.Duration;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;
import org.ta4j.core.Bar;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BarSeries;

/** Thread-safe buffer for maintaining recent market data. */
final class CandleBuffer {
    private final List<Candle> candles = new ArrayList<>();
    
    synchronized void add(Candle candle) {
        candles.add(candle);
    }
    
    synchronized ImmutableList<Candle> getCandles() {
        return ImmutableList.copyOf(candles); 
    }
    
    synchronized BarSeries toBarSeries() {
        var series = new BaseBarSeries();
        for (Candle candle : candles) {
            series.addBar(createBar(candle));
        }
        return series;
    }
    
    private Bar createBar(Candle candle) {
        return new BaseBar(
            Duration.ofMinutes(1),
            Timestamps.toZonedDateTime(candle.getTimestamp()),
            candle.getOpen(),
            candle.getHigh(), 
            candle.getLow(),
            candle.getClose(),
            candle.getVolume()
        );
    }
}
