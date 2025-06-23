package com.verlumen.tradestream.strategies.rangebars;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.RangeBarsParameters;
import org.junit.Test;
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
  public void testCreateStrategy() {
    BaseBarSeries series = new BaseBarSeries();
    RangeBarsParameters params = factory.getDefaultParameters();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.shouldEnter(0)).isFalse();
    assertThat(strategy.shouldExit(0)).isFalse();
  }
} 