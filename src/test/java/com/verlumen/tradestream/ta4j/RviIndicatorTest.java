package com.verlumen.tradestream.ta4j;

import static com.google.common.truth.Truth.assertThat;

import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.indicators.helpers.OpenPriceIndicator;
import org.ta4j.core.num.Num;

@RunWith(JUnit4.class)
public class RviIndicatorTest {
  private BaseBarSeries series;
  private RviIndicator rvi;
  private static final int PERIOD = 10;

  @Before
  public void setUp() {
    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Create bars with upward trend (close > open)
    for (int i = 0; i < 50; i++) {
      double open = 100 + i;
      double high = open + 5;
      double low = open - 2;
      double close = open + 3; // Bullish candles
      series.addBar(
          new BaseBar(Duration.ofMinutes(1), now.plusMinutes(i), open, high, low, close, 1000.0));
    }

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    OpenPriceIndicator openPrice = new OpenPriceIndicator(series);
    HighPriceIndicator highPrice = new HighPriceIndicator(series);
    LowPriceIndicator lowPrice = new LowPriceIndicator(series);

    rvi = new RviIndicator(closePrice, openPrice, highPrice, lowPrice, PERIOD);
  }

  @Test
  public void getValue_beforePeriod_returnsZero() {
    Num value = rvi.getValue(PERIOD - 2);
    assertThat(value.doubleValue()).isEqualTo(0.0);
  }

  @Test
  public void getValue_atPeriod_returnsNonZero() {
    Num value = rvi.getValue(PERIOD);
    assertThat(value.doubleValue()).isNotEqualTo(0.0);
  }

  @Test
  public void getValue_bullishBars_returnsPositive() {
    // With bullish bars (close > open), RVI should be positive
    Num value = rvi.getValue(30);
    assertThat(value.doubleValue()).isGreaterThan(0.0);
  }

  @Test
  public void getUnstableBars_returnsPeriod() {
    assertThat(rvi.getUnstableBars()).isEqualTo(PERIOD);
  }

  @Test
  public void getValue_withZeroRange_handlesGracefully() {
    // Create series with zero range bars (high == low)
    BaseBarSeries zeroRangeSeries = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 20; i++) {
      double price = 100.0;
      zeroRangeSeries.addBar(
          new BaseBar(
              Duration.ofMinutes(1), now.plusMinutes(i), price, price, price, price, 1000.0));
    }

    ClosePriceIndicator closePrice = new ClosePriceIndicator(zeroRangeSeries);
    OpenPriceIndicator openPrice = new OpenPriceIndicator(zeroRangeSeries);
    HighPriceIndicator highPrice = new HighPriceIndicator(zeroRangeSeries);
    LowPriceIndicator lowPrice = new LowPriceIndicator(zeroRangeSeries);

    RviIndicator zeroRvi = new RviIndicator(closePrice, openPrice, highPrice, lowPrice, 5);

    // Should return 0 when all bars have zero range
    Num value = zeroRvi.getValue(15);
    assertThat(value.doubleValue()).isEqualTo(0.0);
  }

  @Test
  public void getValue_bearishBars_returnsNegative() {
    // Create series with bearish bars (close < open)
    BaseBarSeries bearishSeries = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 30; i++) {
      double open = 150 - i;
      double high = open + 2;
      double low = open - 5;
      double close = open - 3; // Bearish candles
      bearishSeries.addBar(
          new BaseBar(Duration.ofMinutes(1), now.plusMinutes(i), open, high, low, close, 1000.0));
    }

    ClosePriceIndicator closePrice = new ClosePriceIndicator(bearishSeries);
    OpenPriceIndicator openPrice = new OpenPriceIndicator(bearishSeries);
    HighPriceIndicator highPrice = new HighPriceIndicator(bearishSeries);
    LowPriceIndicator lowPrice = new LowPriceIndicator(bearishSeries);

    RviIndicator bearishRvi = new RviIndicator(closePrice, openPrice, highPrice, lowPrice, PERIOD);

    Num value = bearishRvi.getValue(20);
    assertThat(value.doubleValue()).isLessThan(0.0);
  }

  @Test
  public void getValue_valuesAreBounded() {
    // RVI values should typically be between -1 and 1
    for (int i = PERIOD; i < series.getBarCount(); i++) {
      Num value = rvi.getValue(i);
      assertThat(value.doubleValue()).isAtLeast(-1.0);
      assertThat(value.doubleValue()).isAtMost(1.0);
    }
  }

  @Test
  public void getValue_consecutiveValues_areCached() {
    // First call
    Num value1 = rvi.getValue(30);
    // Second call to same index should return same cached value
    Num value2 = rvi.getValue(30);
    assertThat(value1).isEqualTo(value2);
  }
}
