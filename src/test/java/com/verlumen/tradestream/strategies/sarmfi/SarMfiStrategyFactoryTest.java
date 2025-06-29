package com.verlumen.tradestream.strategies.sarmfi;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.SarMfiParameters;
import org.junit.Test;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class SarMfiStrategyFactoryTest {
  private final SarMfiStrategyFactory factory = new SarMfiStrategyFactory();

  @Test
  public void testGetDefaultParameters() {
    SarMfiParameters params = factory.getDefaultParameters();
    assertThat(params).isNotNull();
    assertThat(params.hasAccelerationFactorStart()).isTrue();
    assertThat(params.hasAccelerationFactorIncrement()).isTrue();
    assertThat(params.hasAccelerationFactorMax()).isTrue();
    assertThat(params.hasMfiPeriod()).isTrue();
  }

  @Test
  public void testCreateStrategy() {
    BaseBarSeries series = new BaseBarSeries();
    SarMfiParameters params = factory.getDefaultParameters();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNull();
    assertThat(strategy.getExitRule()).isNull();
  }
}
