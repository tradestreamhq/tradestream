package com.verlumen.tradestream.strategies.pivot;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.PivotParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class PivotStrategyFactoryTest {
  private final PivotStrategyFactory factory = new PivotStrategyFactory();

  @Test
  public void testGetDefaultParameters() {
    PivotParameters params = factory.getDefaultParameters();
    assertThat(params).isNotNull();
    assertThat(params.getPeriod()).isEqualTo(20);
  }

  @Test
  public void testCreateStrategy() {
    BarSeries series = new BaseBarSeries();
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
    PivotParameters params = PivotParameters.newBuilder().setPeriod(10).build();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }
}
