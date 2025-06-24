package com.verlumen.tradestream.strategies.regressionchannel;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.RegressionChannelParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class RegressionChannelStrategyFactoryTest {
  private final RegressionChannelStrategyFactory factory = new RegressionChannelStrategyFactory();

  @Test
  public void testGetDefaultParameters() {
    RegressionChannelParameters params = factory.getDefaultParameters();
    assertThat(params).isNotNull();
    assertThat(params.getPeriod()).isEqualTo(20);
  }

  @Test
  public void testCreateStrategy() {
    BarSeries series = new BaseBarSeries();
    // Add some bars
    for (int i = 0; i < 30; i++) {
      series.addBar(
          new BaseBar(
              Duration.ofMinutes(1),
              ZonedDateTime.now().plusMinutes(i),
              100 + i,
              101 + i,
              99 + i,
              100 + i,
              1000));
    }
    RegressionChannelParameters params =
        RegressionChannelParameters.newBuilder().setPeriod(20).build();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }
}
