package com.verlumen.tradestream.ta4j;

import com.verlumen.tradestream.backtesting.GAOptimizationRequest;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import java.time.ZonedDateTime;
import java.time.Duration;

public class BarSeriesBuilder {
  public static BarSeries createBarSeries(ImmutableList<Candle> candles) {
    BaseBarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    candles.forEach(candle ->
        series.addBar(Duration.ofMinutes(1),
            now.plusMinutes(series.getBarCount()),
            candle.getOpen(),
            candle.getHigh(),
            candle.getLow(),
            candle.getClose(),
            candle.getVolume())
    );

    return series;
  }
}
