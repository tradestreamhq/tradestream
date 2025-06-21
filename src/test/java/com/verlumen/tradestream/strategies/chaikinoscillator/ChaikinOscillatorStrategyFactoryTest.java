package com.verlumen.tradestream.strategies.chaikinoscillator;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.ChaikinOscillatorParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public class ChaikinOscillatorStrategyFactoryTest {
  private ChaikinOscillatorStrategyFactory factory;
  private BarSeries series;

  @Before
  public void setUp() {
    factory = new ChaikinOscillatorStrategyFactory();
    series = new BaseBarSeries();
    for (int i = 0; i < 50; i++) {
      series.addBar(
          new BaseBar(
              Duration.ofDays(1), ZonedDateTime.now().plusDays(i), 100 + i, 100 + i, 100 + i, 100 + i, 100));
    }
  }

  @Test
  public void testCreateStrategy() {
    ChaikinOscillatorParameters params =
        ChaikinOscillatorParameters.newBuilder().setFastPeriod(3).setSlowPeriod(10).build();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
  }

  @Test(expected = IllegalArgumentException.class)
  public void testCreateStrategy_negativeFastPeriod() {
    ChaikinOscillatorParameters params =
        ChaikinOscillatorParameters.newBuilder().setFastPeriod(-1).setSlowPeriod(10).build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void testCreateStrategy_slowPeriodLessThanFast() {
    ChaikinOscillatorParameters params =
        ChaikinOscillatorParameters.newBuilder().setFastPeriod(10).setSlowPeriod(5).build();
    factory.createStrategy(series, params);
  }
}
