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
    Instant endTime = getInstant(candle);
    return new BaseBar(
        ONE_MINUTE,
        endTime,
        valueOf(candle.getOpen()),
        valueOf(candle.getHigh()),
        valueOf(candle.getLow()),
        valueOf(candle.getClose()),
        valueOf(candle.getVolume()),
        valueOf(0), // amount - defaulting to 0 since not available in Candle
        0L          // number of trades - defaulting to 0 since not available in Candle
    );
  }

  private static Instant getInstant(Candle candle) {
    long epochMillis = Timestamps.toMillis(candle.getTimestamp());
    return Instant.ofEpochMilli(epochMillis);
  }
}
