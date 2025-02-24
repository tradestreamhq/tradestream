package com.verlumen.tradestream.ta4j;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Timestamp;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.marketdata.Candle;
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
            BarSeriesBuilder.getZonedDateTime(candle),
            candle.getOpen(),
            candle.getHigh(),
            candle.getLow(),
            candle.getClose(),
            candle.getVolume())
    );

    return series;
  }

  private static ZonedDateTime getZonedDateTime(Candle candle) {
    long epochMillis = Timestamps.toMillis(candle.getTimestamp());
    ZonedDateTime zonedDateTime = Instant.ofEpochMilli(epochMillis).atZone(UTC);
  }
}
