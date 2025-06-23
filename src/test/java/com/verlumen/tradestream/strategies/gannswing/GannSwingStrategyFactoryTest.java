package com.verlumen.tradestream.strategies.gannswing;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.GannSwingParameters;
import org.junit.Test;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class GannSwingStrategyFactoryTest {
  private final GannSwingStrategyFactory factory = new GannSwingStrategyFactory();

  @Test
  public void testGetDefaultParameters() {
    GannSwingParameters params = factory.getDefaultParameters();
    assertThat(params).isNotNull();
    assertThat(params.hasGannPeriod()).isTrue();
  }

  @Test
  public void testCreateStrategy() {
    BaseBarSeries series = new BaseBarSeries();
    GannSwingParameters params = factory.getDefaultParameters();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.shouldEnter(0)).isFalse();
    assertThat(strategy.shouldExit(0)).isFalse();
  }
}
