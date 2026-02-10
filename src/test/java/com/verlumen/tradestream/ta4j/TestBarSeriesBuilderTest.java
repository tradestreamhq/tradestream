package com.verlumen.tradestream.ta4j;

import static com.google.common.truth.Truth.assertThat;

import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;

@RunWith(JUnit4.class)
public class TestBarSeriesBuilderTest {

  private static final ZonedDateTime TEST_TIME =
      ZonedDateTime.of(2024, 1, 15, 10, 30, 0, 0, ZoneOffset.UTC);

  @Test
  public void createBarSeries_returnsNonNullSeries() {
    BarSeries series = TestBarSeriesBuilder.createBarSeries();

    assertThat(series).isNotNull();
  }

  @Test
  public void createBarSeries_returnsEmptySeries() {
    BarSeries series = TestBarSeriesBuilder.createBarSeries();

    assertThat(series.getBarCount()).isEqualTo(0);
  }

  @Test
  public void createBarSeries_hasCorrectName() {
    BarSeries series = TestBarSeriesBuilder.createBarSeries();

    assertThat(series.getName()).isEqualTo("testSeries");
  }

  @Test
  public void createBar_withSinglePrice_returnsNonNullBar() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 100.0);

    assertThat(bar).isNotNull();
  }

  @Test
  public void createBar_withSinglePrice_hasMatchingOpenPrice() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 100.0);

    assertThat(bar.getOpenPrice().doubleValue()).isWithin(0.001).of(100.0);
  }

  @Test
  public void createBar_withSinglePrice_hasMatchingHighPrice() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 100.0);

    assertThat(bar.getHighPrice().doubleValue()).isWithin(0.001).of(100.0);
  }

  @Test
  public void createBar_withSinglePrice_hasMatchingLowPrice() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 100.0);

    assertThat(bar.getLowPrice().doubleValue()).isWithin(0.001).of(100.0);
  }

  @Test
  public void createBar_withSinglePrice_hasMatchingClosePrice() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 100.0);

    assertThat(bar.getClosePrice().doubleValue()).isWithin(0.001).of(100.0);
  }

  @Test
  public void createBar_withSinglePrice_hasDefaultVolume() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 100.0);

    assertThat(bar.getVolume().doubleValue()).isWithin(0.001).of(100.0);
  }

  @Test
  public void createBar_withOHLCV_returnsNonNullBar() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 100.0, 110.0, 95.0, 105.0, 1000.0);

    assertThat(bar).isNotNull();
  }

  @Test
  public void createBar_withOHLCV_hasCorrectOpenPrice() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 100.0, 110.0, 95.0, 105.0, 1000.0);

    assertThat(bar.getOpenPrice().doubleValue()).isWithin(0.001).of(100.0);
  }

  @Test
  public void createBar_withOHLCV_hasCorrectHighPrice() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 100.0, 110.0, 95.0, 105.0, 1000.0);

    assertThat(bar.getHighPrice().doubleValue()).isWithin(0.001).of(110.0);
  }

  @Test
  public void createBar_withOHLCV_hasCorrectLowPrice() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 100.0, 110.0, 95.0, 105.0, 1000.0);

    assertThat(bar.getLowPrice().doubleValue()).isWithin(0.001).of(95.0);
  }

  @Test
  public void createBar_withOHLCV_hasCorrectClosePrice() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 100.0, 110.0, 95.0, 105.0, 1000.0);

    assertThat(bar.getClosePrice().doubleValue()).isWithin(0.001).of(105.0);
  }

  @Test
  public void createBar_withOHLCV_hasCorrectVolume() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 100.0, 110.0, 95.0, 105.0, 1000.0);

    assertThat(bar.getVolume().doubleValue()).isWithin(0.001).of(1000.0);
  }

  @Test
  public void createBar_withZeroPrice_works() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 0.0);

    assertThat(bar.getClosePrice().doubleValue()).isWithin(0.001).of(0.0);
  }

  @Test
  public void createBar_withLargePrice_works() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 1000000.0);

    assertThat(bar.getClosePrice().doubleValue()).isWithin(0.001).of(1000000.0);
  }

  @Test
  public void createBar_withSmallPrice_works() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 0.00001);

    assertThat(bar.getClosePrice().doubleValue()).isWithin(0.0000001).of(0.00001);
  }

  @Test
  public void createBarSeries_andAddBar_works() {
    BarSeries series = TestBarSeriesBuilder.createBarSeries();
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 100.0);

    series.addBar(bar);

    assertThat(series.getBarCount()).isEqualTo(1);
    assertThat(series.getBar(0)).isEqualTo(bar);
  }

  @Test
  public void createBar_preservesTimeInstant() {
    Bar bar = TestBarSeriesBuilder.createBar(TEST_TIME, 100.0);

    assertThat(bar.getEndTime()).isEqualTo(TEST_TIME.toInstant());
  }

  @Test
  public void createBar_withDifferentTimes_createsDistinctBars() {
    ZonedDateTime time1 = TEST_TIME;
    ZonedDateTime time2 = TEST_TIME.plusMinutes(1);

    Bar bar1 = TestBarSeriesBuilder.createBar(time1, 100.0);
    Bar bar2 = TestBarSeriesBuilder.createBar(time2, 100.0);

    assertThat(bar1.getEndTime()).isNotEqualTo(bar2.getEndTime());
  }
}
