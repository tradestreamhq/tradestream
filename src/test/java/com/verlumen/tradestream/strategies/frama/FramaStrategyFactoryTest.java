package com.verlumen.tradestream.strategies.frama;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.FramaParameters;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;

public final class FramaStrategyFactoryTest {
  private final FramaStrategyFactory factory = new FramaStrategyFactory();

  @Test
  public void testGetDefaultParameters() {
    FramaParameters params = factory.getDefaultParameters();
    assertThat(params.getSc()).isEqualTo(0.5);
    assertThat(params.getFc()).isEqualTo(20);
    assertThat(params.getAlpha()).isEqualTo(0.5);
  }

  @Test
  public void testCreateStrategy() {
    BarSeries series = new BaseBarSeriesBuilder().withName("test").build();
    FramaParameters params = factory.getDefaultParameters();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }
}
