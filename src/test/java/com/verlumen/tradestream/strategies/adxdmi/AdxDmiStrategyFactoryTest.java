package com.verlumen.tradestream.strategies.adxdmi;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.AdxDmiParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public class AdxDmiStrategyFactoryTest {
  private AdxDmiStrategyFactory factory;
  private BarSeries series;

  @Before
  public void setUp() {
    factory = new AdxDmiStrategyFactory();
    series = new BaseBarSeries();
    for (int i = 0; i < 50; i++) {
      series.addBar(
          new BaseBar(
              Duration.ofDays(1),
              ZonedDateTime.now().plusDays(i),
              100 + i,
              100 + i,
              100 + i,
              100 + i,
              100));
    }
  }

  @Test
  public void testCreateStrategy() {
    AdxDmiParameters params =
        AdxDmiParameters.newBuilder().setAdxPeriod(14).setDiPeriod(14).build();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
  }

  @Test(expected = IllegalArgumentException.class)
  public void testCreateStrategy_negativeAdxPeriod() {
    AdxDmiParameters params =
        AdxDmiParameters.newBuilder().setAdxPeriod(-1).setDiPeriod(14).build();
    factory.createStrategy(series, params);
  }
}
