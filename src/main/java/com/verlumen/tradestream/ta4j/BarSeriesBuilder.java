package com.verlumen.tradestream.ta4j;

import static org.ta4j.core.num.DecimalNum.valueOf;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.marketdata.Candle;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeriesBuilder;

final class BarSeriesBuilder {
  private static Duration ONE_MINUTE = Duration.ofMinutes(1);
  private static ZoneId UTC = ZoneId.of("UTC");

  public static BarSeries createBarSeries(ImmutableList<Candle> candles) {
    BarSeries series = new BaseBarSeriesBuilder()
        .withName("candleSeries")
        .build();
    
    candles.stream()
        .map(BarSeriesBuilder::createBar)
        .forEach(series::addBar);

    return series;
  }

  private static Bar createBar(Candle candle) {
    ZonedDateTime endTime = getZonedDateTime(candle);
    return new BaseBar(
        ONE_MINUTE,
        endTime,
        candle.getOpen(),
        candle.getHigh(),
        candle.getLow(),
        candle.getClose(),
        candle.getVolume()
    );
  }

  private static ZonedDateTime getZonedDateTime(Candle candle) {
    long epochMillis = Timestamps.toMillis(candle.getTimestamp());
    return Instant.ofEpochMilli(epochMillis).atZone(UTC);
  }
}
