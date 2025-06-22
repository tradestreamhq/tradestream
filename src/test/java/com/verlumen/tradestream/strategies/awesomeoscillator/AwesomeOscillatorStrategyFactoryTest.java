package com.verlumen.tradestream.strategies.awesomeoscillator;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.AwesomeOscillatorParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public class AwesomeOscillatorStrategyFactoryTest {
  private AwesomeOscillatorStrategyFactory factory;
  private BarSeries series;

  @Before
  public void setUp() {
    factory = new AwesomeOscillatorStrategyFactory();
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
    AwesomeOscillatorParameters params =
        AwesomeOscillatorParameters.newBuilder().setShortPeriod(5).setLongPeriod(34).build();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
  }

  @Test(expected = IllegalArgumentException.class)
  public void testCreateStrategy_negativeShortPeriod() {
    AwesomeOscillatorParameters params =
        AwesomeOscillatorParameters.newBuilder().setShortPeriod(-1).setLongPeriod(34).build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void testCreateStrategy_longPeriodLessThanShort() {
    AwesomeOscillatorParameters params =
        AwesomeOscillatorParameters.newBuilder().setShortPeriod(10).setLongPeriod(5).build();
    factory.createStrategy(series, params);
  }
}
