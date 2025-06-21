package com.verlumen.tradestream.strategies.aroonmfi;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.AroonMfiParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public class AroonMfiStrategyFactoryTest {
  private AroonMfiStrategyFactory factory;
  private BarSeries series;

  @Before
  public void setUp() {
    factory = new AroonMfiStrategyFactory();
    series = new BaseBarSeries();
    for (int i = 0; i < 50; i++) {
      series.addBar(
          new BaseBar(
              Duration.ofDays(1), ZonedDateTime.now().plusDays(i), 100 + i, 100 + i, 100 + i, 100 + i, 100));
    }
  }

  @Test
  public void testCreateStrategy() {
    AroonMfiParameters params =
        AroonMfiParameters.newBuilder()
            .setAroonPeriod(25)
            .setMfiPeriod(14)
            .setOverboughtThreshold(80)
            .setOversoldThreshold(20)
            .build();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
  }

  @Test(expected = IllegalArgumentException.class)
  public void testCreateStrategy_negativeAroonPeriod() {
    AroonMfiParameters params =
        AroonMfiParameters.newBuilder().setAroonPeriod(-1).setMfiPeriod(14).build();
    factory.createStrategy(series, params);
  }
}
