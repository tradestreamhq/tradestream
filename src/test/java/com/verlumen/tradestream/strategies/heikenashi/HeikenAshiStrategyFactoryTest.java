package com.verlumen.tradestream.strategies.heikenashi;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.HeikenAshiParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

@RunWith(JUnit4.class)
public class HeikenAshiStrategyFactoryTest {
  private HeikenAshiStrategyFactory factory;
  private HeikenAshiParameters params;
  private BaseBarSeries series;

  @Before
  public void setUp() {
    factory = new HeikenAshiStrategyFactory();
    params = HeikenAshiParameters.newBuilder().setPeriod(14).build();
    series = new BaseBarSeries();
    // Add some bars
    for (int i = 0; i < 20; i++) {
      series.addBar(
          new BaseBar(
              Duration.ofMinutes(1), ZonedDateTime.now().plusMinutes(i), 1, 2, 0.5, 1.5, 100));
    }
  }

  @Test
  public void testCreateStrategy_returnsNonNull() {
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
  }

  @Test(expected = IllegalArgumentException.class)
  public void testCreateStrategy_invalidParams_throws() {
    HeikenAshiParameters badParams = HeikenAshiParameters.newBuilder().setPeriod(0).build();
    factory.createStrategy(series, badParams);
  }
}
