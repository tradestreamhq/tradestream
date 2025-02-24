package com.verlumen.tradestream.ta4j;

import static org.ta4j.core.num.DecimalNum.valueOf;

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

    candles
      .stream()
      .map(BarSeriesBuilder::createBar)
      .forEach(series::addBar);

    return series;
  }

  private static Bar createBar(Candle candle) {
    ZonedDateTime dateTime = getZonedDateTime(candle);
    return BaseBar.builder()
        .timePeriod(ONE_MINUTE)
        .endTime(dateTime.plus(ONE_MINUTE))
        .openPrice(valueOf(candle.getOpen()))
        .highPrice(valueOf(candle.getHigh()))
        .lowPrice(valueOf(candle.getLow()))
        .closePrice(valueOf(candle.getClose()))
        .volume(valueOf(candle.getVolume()))
        .build();
  }

  private static ZonedDateTime getZonedDateTime(Candle candle) {
    long epochMillis = Timestamps.toMillis(candle.getTimestamp());
    return Instant.ofEpochMilli(epochMillis).atZone(UTC);
  }
}
