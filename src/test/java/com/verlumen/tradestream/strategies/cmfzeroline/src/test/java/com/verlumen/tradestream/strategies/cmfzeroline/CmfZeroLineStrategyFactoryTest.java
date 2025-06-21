package com.verlumen.tradestream.strategies.cmfzeroline;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.CmfZeroLineParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public class CmfZeroLineStrategyFactoryTest {
  private CmfZeroLineStrategyFactory factory;
  private BarSeries series;

  @Before
  public void setUp() {
    factory = new CmfZeroLineStrategyFactory();
    series = new BaseBarSeries();
    for (int i = 0; i < 50; i++) {
      series.addBar(
          new BaseBar(
              Duration.ofDays(1), ZonedDateTime.now().plusDays(i), 100 + i, 100 + i, 100 + i, 100 + i, 100));
    }
  }

  @Test
  public void testCreateStrategy() {
    CmfZeroLineParameters params = CmfZeroLineParameters.newBuilder().setPeriod(20).build();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
  }

  @Test(expected = IllegalArgumentException.class)
  public void testCreateStrategy_negativePeriod() {
    CmfZeroLineParameters params = CmfZeroLineParameters.newBuilder().setPeriod(-1).build();
    factory.createStrategy(series, params);
  }
}
