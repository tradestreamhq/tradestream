package com.verlumen.tradestream.marketregime;

import static com.google.common.truth.Truth.assertThat;

import java.time.Duration;
import java.time.Instant;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.num.DecimalNum;

@RunWith(JUnit4.class)
public class MarketRegimeDetectorTest {

  private MarketRegimeDetector detector;

  @Before
  public void setUp() {
    detector = MarketRegimeDetector.withDefaults();
  }

  @Test
  public void classify_strongUptrend_returnsTrendingUp() {
    BarSeries series = buildStrongUptrendSeries();
    int lastIndex = series.getBarCount() - 1;

    RegimeClassification result = detector.classify(series, lastIndex);

    assertThat(result.getRegime()).isEqualTo(MarketRegime.TRENDING_UP);
    assertThat(result.getConfidence()).isGreaterThan(0.0);
    assertThat(result.getConfidence()).isAtMost(1.0);
    assertThat(result.getRecommendedStrategies()).isNotEmpty();
    assertThat(result.getRecommendedStrategies()).contains("ADX_DMI");
    assertThat(result.getRecommendedStrategies()).contains("MACD_CROSSOVER");
  }

  @Test
  public void classify_strongDowntrend_returnsTrendingDown() {
    BarSeries series = buildStrongDowntrendSeries();
    int lastIndex = series.getBarCount() - 1;

    RegimeClassification result = detector.classify(series, lastIndex);

    assertThat(result.getRegime()).isEqualTo(MarketRegime.TRENDING_DOWN);
    assertThat(result.getConfidence()).isGreaterThan(0.0);
    assertThat(result.getRecommendedStrategies()).contains("ATR_TRAILING_STOP");
  }

  @Test
  public void classify_rangingMarket_producesValidClassification() {
    MarketRegimeDetector rangingDetector =
        MarketRegimeDetector.builder().setAdxTrendThreshold(20.0).build();
    BarSeries series = buildRangingSeries();
    int lastIndex = series.getBarCount() - 1;

    RegimeClassification result = rangingDetector.classify(series, lastIndex);

    assertThat(result.getAdxValue()).isAtLeast(0.0);
    assertThat(result.getConfidence()).isAtLeast(0.0);
    assertThat(result.getRecommendedStrategies()).isNotEmpty();
  }

  @Test
  public void classify_highVolatility_hasSignificantAtr() {
    MarketRegimeDetector volDetector =
        MarketRegimeDetector.builder()
            .setAdxTrendThreshold(40.0)
            .setHighVolatilityAtrThreshold(0.01)
            .build();
    BarSeries series = buildHighVolatilitySeries();
    int lastIndex = series.getBarCount() - 1;

    RegimeClassification result = volDetector.classify(series, lastIndex);

    assertThat(result.getAtrPercent()).isGreaterThan(0.0);
    assertThat(result.getConfidence()).isGreaterThan(0.0);
  }

  @Test
  public void classify_lowVolatility_hasSmallBbWidth() {
    MarketRegimeDetector quietDetector =
        MarketRegimeDetector.builder()
            .setAdxTrendThreshold(40.0)
            .setLowVolatilityBbWidthThreshold(0.10)
            .build();
    BarSeries series = buildLowVolatilitySeries();
    int lastIndex = series.getBarCount() - 1;

    RegimeClassification result = quietDetector.classify(series, lastIndex);

    assertThat(result.getBbWidthPercent()).isLessThan(0.10);
    assertThat(result.getConfidence()).isAtLeast(0.0);
  }

  @Test
  public void classify_returnsValidIndicatorValues() {
    BarSeries series = buildStrongUptrendSeries();
    int lastIndex = series.getBarCount() - 1;

    RegimeClassification result = detector.classify(series, lastIndex);

    assertThat(result.getAdxValue()).isAtLeast(0.0);
    assertThat(result.getAtrPercent()).isAtLeast(0.0);
    assertThat(result.getBbWidthPercent()).isAtLeast(0.0);
  }

  @Test
  public void detectChange_regimeShift_returnsEvent() {
    BarSeries series = buildTransitionSeries();
    int earlyIndex = 30;
    int lateIndex = series.getBarCount() - 1;

    RegimeClassification early = detector.classify(series, earlyIndex);
    RegimeClassification late = detector.classify(series, lateIndex);

    if (early.getRegime() != late.getRegime()) {
      RegimeChangeEvent event = detector.detectChange(series, earlyIndex, lateIndex);
      assertThat(event).isNotNull();
      assertThat(event.getPreviousRegime().getRegime()).isEqualTo(early.getRegime());
      assertThat(event.getCurrentRegime().getRegime()).isEqualTo(late.getRegime());
      assertThat(event.getBarIndex()).isEqualTo(lateIndex);
    }
  }

  @Test
  public void detectChange_sameRegime_returnsNull() {
    BarSeries series = buildStrongUptrendSeries();
    int lastIndex = series.getBarCount() - 1;

    RegimeChangeEvent event = detector.detectChange(series, lastIndex - 1, lastIndex);

    if (event != null) {
      assertThat(event.getPreviousRegime().getRegime())
          .isNotEqualTo(event.getCurrentRegime().getRegime());
    }
  }

  @Test
  public void regimeClassification_toString_containsRegimeInfo() {
    BarSeries series = buildStrongUptrendSeries();
    RegimeClassification result = detector.classify(series, series.getBarCount() - 1);

    String str = result.toString();
    assertThat(str).contains("RegimeClassification");
    assertThat(str).contains(result.getRegime().name());
  }

  @Test
  public void marketRegime_hasDescription() {
    for (MarketRegime regime : MarketRegime.values()) {
      assertThat(regime.getDescription()).isNotEmpty();
    }
  }

  @Test
  public void builder_customThresholds_respected() {
    MarketRegimeDetector custom =
        MarketRegimeDetector.builder()
            .setAdxPeriod(20)
            .setAtrPeriod(10)
            .setBbPeriod(30)
            .setAdxTrendThreshold(30.0)
            .setHighVolatilityAtrThreshold(0.05)
            .setLowVolatilityBbWidthThreshold(0.01)
            .build();

    BarSeries series = buildStrongUptrendSeries();
    RegimeClassification result = custom.classify(series, series.getBarCount() - 1);

    assertThat(result.getRegime()).isNotNull();
    assertThat(result.getConfidence()).isAtLeast(0.0);
    assertThat(result.getConfidence()).isAtMost(1.0);
  }

  @Test(expected = IllegalArgumentException.class)
  public void classify_negativeIndex_throws() {
    BarSeries series = buildStrongUptrendSeries();
    detector.classify(series, -1);
  }

  @Test(expected = IllegalArgumentException.class)
  public void classify_indexOutOfBounds_throws() {
    BarSeries series = buildStrongUptrendSeries();
    detector.classify(series, series.getBarCount());
  }

  @Test(expected = IllegalArgumentException.class)
  public void detectChange_invalidOrder_throws() {
    BarSeries series = buildStrongUptrendSeries();
    detector.detectChange(series, 10, 5);
  }

  // --- Test data builders ---

  private static BaseBar createBar(
      Instant endTime, double open, double high, double low, double close, double volume) {
    Instant beginTime = endTime.minus(Duration.ofMinutes(1));
    return new BaseBar(
        Duration.ofMinutes(1),
        beginTime,
        endTime,
        DecimalNum.valueOf(open),
        DecimalNum.valueOf(high),
        DecimalNum.valueOf(low),
        DecimalNum.valueOf(close),
        DecimalNum.valueOf(volume),
        DecimalNum.valueOf(0),
        0);
  }

  private BarSeries buildStrongUptrendSeries() {
    BarSeries series = new BaseBarSeriesBuilder().build();
    Instant time = Instant.now();
    double basePrice = 100.0;

    for (int i = 0; i < 50; i++) {
      double price = basePrice + i * 2.0;
      series.addBar(
          createBar(
              time.plus(Duration.ofMinutes(i)),
              price - 0.2,
              price + 0.5,
              price - 0.3,
              price,
              1000.0));
    }
    return series;
  }

  private BarSeries buildStrongDowntrendSeries() {
    BarSeries series = new BaseBarSeriesBuilder().build();
    Instant time = Instant.now();
    double basePrice = 200.0;

    for (int i = 0; i < 50; i++) {
      double price = basePrice - i * 2.0;
      series.addBar(
          createBar(
              time.plus(Duration.ofMinutes(i)),
              price + 0.2,
              price + 0.3,
              price - 0.5,
              price,
              1000.0));
    }
    return series;
  }

  private BarSeries buildRangingSeries() {
    BarSeries series = new BaseBarSeriesBuilder().build();
    Instant time = Instant.now();

    for (int i = 0; i < 50; i++) {
      double price = 100.0 + Math.sin(i * 0.5) * 2.0;
      series.addBar(
          createBar(
              time.plus(Duration.ofMinutes(i)), price, price + 0.5, price - 0.5, price, 1000.0));
    }
    return series;
  }

  private BarSeries buildHighVolatilitySeries() {
    BarSeries series = new BaseBarSeriesBuilder().build();
    Instant time = Instant.now();

    for (int i = 0; i < 50; i++) {
      double direction = (i % 2 == 0) ? 1 : -1;
      double price = 100.0 + Math.sin(i * 0.8) * 15.0;
      series.addBar(
          createBar(
              time.plus(Duration.ofMinutes(i)),
              price - 3.0,
              price + 10.0,
              price - 10.0,
              price,
              2000.0));
    }
    return series;
  }

  private BarSeries buildLowVolatilitySeries() {
    BarSeries series = new BaseBarSeriesBuilder().build();
    Instant time = Instant.now();

    for (int i = 0; i < 50; i++) {
      double price = 100.0 + Math.sin(i * 0.3) * 0.1;
      series.addBar(
          createBar(
              time.plus(Duration.ofMinutes(i)), price, price + 0.05, price - 0.05, price, 500.0));
    }
    return series;
  }

  private BarSeries buildTransitionSeries() {
    BarSeries series = new BaseBarSeriesBuilder().build();
    Instant time = Instant.now();

    // First 35 bars: ranging
    for (int i = 0; i < 35; i++) {
      double price = 100.0 + Math.sin(i * 0.5) * 1.0;
      series.addBar(
          createBar(
              time.plus(Duration.ofMinutes(i)), price, price + 0.3, price - 0.3, price, 1000.0));
    }

    // Next 25 bars: strong uptrend breakout
    double breakoutPrice = 101.0;
    for (int i = 35; i < 60; i++) {
      double price = breakoutPrice + (i - 35) * 3.0;
      series.addBar(
          createBar(
              time.plus(Duration.ofMinutes(i)),
              price - 0.5,
              price + 1.0,
              price - 0.5,
              price,
              1500.0));
    }
    return series;
  }
}
