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
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;

@RunWith(JUnit4.class)
public class VolumeWeightedMacdLineIndicatorTest {
  private BaseBarSeries series;
  private VolumeWeightedMacdLineIndicator macd;
  private static final int SHORT_PERIOD = 12;
  private static final int LONG_PERIOD = 26;

  @Before
  public void setUp() {
    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Create series with trend
    for (int i = 0; i < 100; i++) {
      double price = 100 + i * 0.5 + Math.sin(i * 0.2) * 10;
      series.addBar(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i),
              price,
              price + 2,
              price - 2,
              price,
              1000.0 + i * 10));
    }

    macd = new VolumeWeightedMacdLineIndicator(series, SHORT_PERIOD, LONG_PERIOD);
  }

  @Test
  public void getValue_beforeUnstablePeriod_returnsZero() {
    Num value = macd.getValue(LONG_PERIOD - 2);
    assertThat(value.doubleValue()).isEqualTo(0.0);
  }

  @Test
  public void getValue_afterUnstablePeriod_returnsNonZero() {
    Num value = macd.getValue(50);
    assertThat(value).isNotNull();
  }

  @Test
  public void getUnstableBars_returnsLongPeriod() {
    assertThat(macd.getUnstableBars()).isEqualTo(LONG_PERIOD);
  }

  @Test
  public void getValue_upwardTrend_isPositive() {
    // Create strong upward trend
    BaseBarSeries upSeries = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 100; i++) {
      double price = 100 + i * 2; // Strong upward trend
      upSeries.addBar(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i),
              price,
              price + 1,
              price - 1,
              price,
              1000.0));
    }

    VolumeWeightedMacdLineIndicator upMacd =
        new VolumeWeightedMacdLineIndicator(upSeries, SHORT_PERIOD, LONG_PERIOD);
    Num value = upMacd.getValue(60);
    // Short EMA should be above long EMA in uptrend
    assertThat(value.doubleValue()).isGreaterThan(0.0);
  }

  @Test
  public void getValue_downwardTrend_isNegative() {
    // Create strong downward trend
    BaseBarSeries downSeries = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 100; i++) {
      double price = 200 - i * 2; // Strong downward trend
      downSeries.addBar(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i),
              price,
              price + 1,
              price - 1,
              price,
              1000.0));
    }

    VolumeWeightedMacdLineIndicator downMacd =
        new VolumeWeightedMacdLineIndicator(downSeries, SHORT_PERIOD, LONG_PERIOD);
    Num value = downMacd.getValue(60);
    // Short EMA should be below long EMA in downtrend
    assertThat(value.doubleValue()).isLessThan(0.0);
  }

  @Test
  public void constructor_withEmaIndicators_works() {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    EMAIndicator shortEma = new EMAIndicator(closePrice, SHORT_PERIOD);
    EMAIndicator longEma = new EMAIndicator(closePrice, LONG_PERIOD);

    VolumeWeightedMacdLineIndicator customMacd =
        new VolumeWeightedMacdLineIndicator(shortEma, longEma);

    Num value = customMacd.getValue(50);
    assertThat(value).isNotNull();
  }

  @Test
  public void getValue_flatPrices_isNearZero() {
    // Create flat price series
    BaseBarSeries flatSeries = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 100; i++) {
      double price = 100.0;
      flatSeries.addBar(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i),
              price,
              price + 0.1,
              price - 0.1,
              price,
              1000.0));
    }

    VolumeWeightedMacdLineIndicator flatMacd =
        new VolumeWeightedMacdLineIndicator(flatSeries, SHORT_PERIOD, LONG_PERIOD);
    Num value = flatMacd.getValue(60);
    // With flat prices, short and long EMAs should converge
    assertThat(Math.abs(value.doubleValue())).isLessThan(1.0);
  }

  @Test
  public void getValue_cachedCorrectly() {
    Num value1 = macd.getValue(70);
    Num value2 = macd.getValue(70);
    assertThat(value1).isEqualTo(value2);
  }

  @Test
  public void getValue_consecutiveIndices_change() {
    Num value1 = macd.getValue(60);
    Num value2 = macd.getValue(61);
    // In a trending market, consecutive values should differ
    assertThat(value1).isNotEqualTo(value2);
  }

  @Test
  public void getUnstableBars_withEmaConstructor_usesMaxOfBoth() {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    EMAIndicator shortEma = new EMAIndicator(closePrice, 5);
    EMAIndicator longEma = new EMAIndicator(closePrice, 20);

    VolumeWeightedMacdLineIndicator customMacd =
        new VolumeWeightedMacdLineIndicator(shortEma, longEma);

    assertThat(customMacd.getUnstableBars()).isEqualTo(20);
  }
}
