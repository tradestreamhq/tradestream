package com.verlumen.tradestream.strategies.renkochart;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.RenkoChartParameters;
import org.junit.Test;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class RenkoChartStrategyFactoryTest {
  private final RenkoChartStrategyFactory factory = new RenkoChartStrategyFactory();

  @Test
  public void testGetDefaultParameters() {
    RenkoChartParameters params = factory.getDefaultParameters();
    assertThat(params).isNotNull();
    assertThat(params.hasBrickSize()).isTrue();
  }

  @Test
  public void testCreateStrategy() {
    BaseBarSeries series = new BaseBarSeries();
    RenkoChartParameters params = factory.getDefaultParameters();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }
}
