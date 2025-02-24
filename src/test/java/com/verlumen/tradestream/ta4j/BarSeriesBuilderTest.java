package com.verlumen.tradestream.ta4j;

import static org.junit.Assert.assertEquals;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Timestamp;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.marketdata.Candle;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;

/**
 * Unit tests for BarSeriesBuilder.
 * Each test uses the AAA pattern with one assertion per test case.
 */
public class BarSeriesBuilderTest {

  /**
   * Helper method to build a real Candle using its protobuf builder.
   *
   * @param epochMillis timestamp in milliseconds
   * @param open        open value
   * @param high        high value
   * @param low         low value
   * @param close       close value
   * @param volume      volume value
   * @return a Candle protobuf message
   */
  private Candle buildCandle(long epochMillis, double open, double high, double low, double close, double volume) {
    Timestamp ts = Timestamps.fromMillis(epochMillis);
    return Candle.newBuilder()
        .setTimestamp(ts)
        .setOpen(open)
        .setHigh(high)
        .setLow(low)
        .setClose(close)
        .setVolume(volume)
        .build();
  }

  @Test
  public void testEmptyCandleListReturnsEmptySeries() {
    // Arrange: create an empty list of candles
    ImmutableList<Candle> candles = ImmutableList.of();
    // Act: build the bar series from an empty list
    BarSeries series = BarSeriesBuilder.createBarSeries(candles);
    // Assert: the series should have no bars
    assertEquals("Bar series should be empty", 0, series.getBarCount());
  }

  @Test
  public void testSingleCandleAddsOneBar() {
    // Arrange: create one real candle
    Candle candle = buildCandle(1609459200000L, 100.0, 110.0, 90.0, 105.0, 1000.0);
    ImmutableList<Candle> candles = ImmutableList.of(candle);
    // Act: build the bar series
    BarSeries series = BarSeriesBuilder.createBarSeries(candles);
    // Assert: the series should contain exactly one bar
    assertEquals("Bar series should contain one bar", 1, series.getBarCount());
  }

  @Test
  public void testBarOpenValueMatchesCandle() {
    // Arrange
    double open = 50.0;
    Candle candle = buildCandle(1609459200000L, open, 55.0, 45.0, 52.0, 500.0);
    ImmutableList<Candle> candles = ImmutableList.of(candle);
    // Act
    BarSeries series = BarSeriesBuilder.createBarSeries(candles);
    Bar bar = series.getBar(0);
    // Assert: bar open value equals candle open value
    assertEquals("Bar open value should match", open, bar.getOpenPrice().doubleValue(), 0.0001);
  }

  @Test
  public void testBarHighValueMatchesCandle() {
    // Arrange
    double high = 120.0;
    Candle candle = buildCandle(1609459200000L, 100.0, high, 80.0, 110.0, 1500.0);
    ImmutableList<Candle> candles = ImmutableList.of(candle);
    // Act
    BarSeries series = BarSeriesBuilder.createBarSeries(candles);
    Bar bar = series.getBar(0);
    // Assert: bar high value equals candle high value
    assertEquals("Bar high value should match", high, bar.getHighPrice().doubleValue(), 0.0001);
  }

  @Test
  public void testBarLowValueMatchesCandle() {
    // Arrange
    double low = 70.0;
    Candle candle = buildCandle(1609459200000L, 90.0, 100.0, low, 95.0, 800.0);
    ImmutableList<Candle> candles = ImmutableList.of(candle);
    // Act
    BarSeries series = BarSeriesBuilder.createBarSeries(candles);
    Bar bar = series.getBar(0);
    // Assert: bar low value equals candle low value
    assertEquals("Bar low value should match", low, bar.getLowPrice().doubleValue(), 0.0001);
  }

  @Test
  public void testBarCloseValueMatchesCandle() {
    // Arrange
    double close = 102.0;
    Candle candle = buildCandle(1609459200000L, 98.0, 105.0, 95.0, close, 900.0);
    ImmutableList<Candle> candles = ImmutableList.of(candle);
    // Act
    BarSeries series = BarSeriesBuilder.createBarSeries(candles);
    Bar bar = series.getBar(0);
    // Assert: bar close value equals candle close value
    assertEquals("Bar close value should match", close, bar.getClosePrice().doubleValue(), 0.0001);
  }

  @Test
  public void testBarVolumeMatchesCandle() {
    // Arrange
    double volume = 2000.0;
    Candle candle = buildCandle(1609459200000L, 100.0, 110.0, 95.0, 105.0, volume);
    ImmutableList<Candle> candles = ImmutableList.of(candle);
    // Act
    BarSeries series = BarSeriesBuilder.createBarSeries(candles);
    Bar bar = series.getBar(0);
    // Assert: bar volume equals candle volume
    assertEquals("Bar volume should match", volume, bar.getVolume().doubleValue(), 0.0001);
  }

  @Test
  public void testMultipleCandlesCreatesMultipleBars() {
    // Arrange: create two candles with sequential timestamps
    Candle candle1 = buildCandle(1609459200000L, 100.0, 110.0, 90.0, 105.0, 1000.0);
    Candle candle2 = buildCandle(1609459260000L, 105.0, 115.0, 95.0, 110.0, 1500.0);
    ImmutableList<Candle> candles = ImmutableList.of(candle1, candle2);
    // Act
    BarSeries series = BarSeriesBuilder.createBarSeries(candles);
    // Assert: series should have two bars
    assertEquals("Bar series should contain two bars", 2, series.getBarCount());
  }

  @Test
  public void testZonedDateTimeConversionIsCorrect() {
    // Arrange: create a candle with a known timestamp
    long epochMillis = 1609459200000L; // Jan 1, 2021 00:00:00 UTC
    Candle candle = buildCandle(epochMillis, 100.0, 110.0, 90.0, 105.0, 1000.0);
    ImmutableList<Candle> candles = ImmutableList.of(candle);
    // Act
    BarSeries series = BarSeriesBuilder.createBarSeries(candles);
    Bar bar = series.getBar(0);
    ZonedDateTime actualDateTime = bar.getBeginTime();
    ZonedDateTime expectedDateTime = Instant.ofEpochMilli(epochMillis).atZone(ZoneId.of("UTC"));
    // Assert: the bar's start time is correctly converted to UTC ZonedDateTime
    assertEquals("Bar start time should be correctly converted", expectedDateTime, actualDateTime);
  }
}
