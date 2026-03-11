package com.verlumen.tradestream.strategies.rangebars;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.verlumen.tradestream.strategies.RangeBarsParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class RangeBarsStrategyFactoryTest {
  private final RangeBarsStrategyFactory factory = new RangeBarsStrategyFactory();

  @Test
  public void testGetDefaultParameters() {
    RangeBarsParameters params = factory.getDefaultParameters();
    assertThat(params).isNotNull();
    assertThat(params.hasRangeSize()).isTrue();
  }

  @Test
  public void testCreateStrategy_returnsStrategyWithRules() {
    BaseBarSeries series = createTestSeries();
    RangeBarsParameters params = factory.getDefaultParameters();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
    assertThat(strategy.getName()).contains("RANGE_BARS");
  }

  @Test
  public void testCreateStrategy_canEvaluateSignals() {
    BaseBarSeries series = createTestSeries();
    RangeBarsParameters params = factory.getDefaultParameters();
    Strategy strategy = factory.createStrategy(series, params);
    for (int i = 0; i < series.getBarCount(); i++) {
      strategy.shouldEnter(i);
      strategy.shouldExit(i);
    }
  }

  @Test
  public void testCreateStrategy_invalidRangeSize_throws() {
    BaseBarSeries series = createTestSeries();
    RangeBarsParameters params = RangeBarsParameters.newBuilder().setRangeSize(0).build();
    assertThrows(IllegalArgumentException.class, () -> factory.createStrategy(series, params));
  }

  private static BaseBarSeries createTestSeries() {
    BaseBarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 50; i++) {
      double price = 100 + Math.sin(i * 0.2) * 10;
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
    return series;
  }
}
