package com.verlumen.tradestream.ta4j;

import com.google.common.collect.ImmutableList;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import java.time.Duration;
import java.time.Instant;
import java.time.ZonedDateTime;
import java.time.ZoneId;

public class BarSeriesBuilder {
  private static Duration ONE_MINUTE = Duration.ofMinutes(1);
  private static ZoneId UTC = ZoneId.of("UTC");

  public static BarSeries createBarSeries(ImmutableList<Candle> candles) {
    BaseBarSeries series = new BaseBarSeries();

    candles.forEach(candle ->
        series.addBar(ONE_MINUTE,
            BarSeriesBuilder.toZonedDateTime(candle.getTimestamp()),
            candle.getOpen(),
            candle.getHigh(),
            candle.getLow(),
            candle.getClose(),
            candle.getVolume())
    );

    return series;
  }

  private static ZonedDateTime toZonedDateTime(Timestamp timestamp) {
    long epochMillis = Timestamps.toMillis(timestamp);
    ZonedDateTime zonedDateTime = Instant.ofEpochMilli(epochMillis).atZone(UTC);
  }
}
