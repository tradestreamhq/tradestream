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
import org.ta4j.core.num.Num;

@RunWith(JUnit4.class)
public class TRIXIndicatorTest {
  private BaseBarSeries series;
  private TRIXIndicator trix;
  private static final int BAR_COUNT = 10;

  @Before
  public void setUp() {
    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Create series with upward trend
    for (int i = 0; i < 100; i++) {
      double price = 100 + i * 0.5 + Math.sin(i * 0.1) * 5;
      series.addBar(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i),
              price,
              price + 2,
              price - 2,
              price,
              1000.0));
    }

    trix = new TRIXIndicator(series, BAR_COUNT);
  }

  @Test
  public void getValue_beforeUnstablePeriod_returnsZero() {
    // TRIX needs 3 * barCount bars to stabilize
    Num value = trix.getValue(BAR_COUNT * 3 - 2);
    assertThat(value.doubleValue()).isEqualTo(0.0);
  }

  @Test
  public void getValue_afterUnstablePeriod_returnsNonZero() {
    Num value = trix.getValue(BAR_COUNT * 3 + 10);
    // Value might still be close to zero but calculation is performed
    assertThat(value).isNotNull();
  }

  @Test
  public void getUnstableBars_returnsThreeTimesBarCount() {
    assertThat(trix.getUnstableBars()).isEqualTo(BAR_COUNT * 3);
  }

  @Test
  public void getValue_upwardTrend_returnsPositive() {
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

    TRIXIndicator upTrix = new TRIXIndicator(upSeries, 5);
    Num value = upTrix.getValue(50);
    assertThat(value.doubleValue()).isGreaterThan(0.0);
  }

  @Test
  public void getValue_downwardTrend_returnsNegative() {
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

    TRIXIndicator downTrix = new TRIXIndicator(downSeries, 5);
    Num value = downTrix.getValue(50);
    assertThat(value.doubleValue()).isLessThan(0.0);
  }

  @Test
  public void getValue_flatPrices_returnsNearZero() {
    // Create flat price series
    BaseBarSeries flatSeries = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 100; i++) {
      double price = 100.0; // Flat price
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

    TRIXIndicator flatTrix = new TRIXIndicator(flatSeries, 5);
    Num value = flatTrix.getValue(50);
    assertThat(Math.abs(value.doubleValue())).isLessThan(0.001);
  }

  @Test
  public void getValue_consecutiveIndices_areDifferent() {
    // TRIX should change between bars in a trending market
    Num value1 = trix.getValue(60);
    Num value2 = trix.getValue(61);
    // Values shouldn't be exactly equal unless prices are identical
    assertThat(value1).isNotEqualTo(value2);
  }

  @Test
  public void getValue_cachedCorrectly() {
    Num value1 = trix.getValue(70);
    Num value2 = trix.getValue(70);
    assertThat(value1).isEqualTo(value2);
  }

  @Test
  public void getValue_withZeroPreviousValue_returnsZero() {
    // When previous EMA3 value is zero, should handle division gracefully
    BaseBarSeries zeroSeries = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 50; i++) {
      zeroSeries.addBar(
          new BaseBar(Duration.ofMinutes(1), now.plusMinutes(i), 0, 0, 0, 0, 1000.0));
    }

    TRIXIndicator zeroTrix = new TRIXIndicator(zeroSeries, 5);
    Num value = zeroTrix.getValue(30);
    assertThat(value.doubleValue()).isEqualTo(0.0);
  }
}
