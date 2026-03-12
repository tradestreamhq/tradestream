package com.verlumen.tradestream.ta4j;

import static org.ta4j.core.num.DecimalNum.valueOf;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.marketdata.Candle;
import java.time.Duration;
import java.time.Instant;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeriesBuilder;

final class BarSeriesBuilder {
  private static Duration ONE_MINUTE = Duration.ofMinutes(1);

  public static BarSeries createBarSeries(ImmutableList<Candle> candles) {
    BarSeries series = new BaseBarSeriesBuilder().build();

    candles.stream().map(BarSeriesBuilder::createBar).forEach(series::addBar);

    return series;
  }

  private static Bar createBar(Candle candle) {
    Instant endTime = getInstant(candle).plus(ONE_MINUTE);
    Instant beginTime = getInstant(candle);
    return new BaseBar(
        ONE_MINUTE,
        beginTime,
        endTime,
        valueOf(candle.getOpen()),
        valueOf(candle.getHigh()),
        valueOf(candle.getLow()),
        valueOf(candle.getClose()),
        valueOf(candle.getVolume()),
        valueOf(0),
        0);
  }

  private static Instant getInstant(Candle candle) {
    long epochMillis = Timestamps.toMillis(candle.getTimestamp());
    return Instant.ofEpochMilli(epochMillis);
  }
}
