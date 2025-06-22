package com.verlumen.tradestream.strategies.linearregressionchannels;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.LinearRegressionChannelsParameters;
import java.time.Duration;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class LinearRegressionChannelsStrategyFactoryTest {
  private LinearRegressionChannelsStrategyFactory factory;
  private BarSeries barSeries;

  @Before
  public void setUp() {
    factory = new LinearRegressionChannelsStrategyFactory();

    List<Bar> bars = new ArrayList<>();
    ZonedDateTime now = ZonedDateTime.now(ZoneId.of("UTC"));
    for (int i = 0; i < 100; i++) {
      bars.add(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i),
              100.0 + i * 0.1,
              100.5 + i * 0.1,
              99.5 + i * 0.1,
              100.2 + i * 0.1,
              1000.0 + i * 10));
    }
    barSeries = new BaseBarSeries(bars);
  }

  @Test
  public void createStrategy_withDefaultParameters_returnsStrategy() {
    LinearRegressionChannelsParameters params = factory.getDefaultParameters();
    Strategy strategy = factory.createStrategy(barSeries, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }

  @Test
  public void createStrategy_withCustomParameters_returnsStrategy() {
    LinearRegressionChannelsParameters params =
        LinearRegressionChannelsParameters.newBuilder().setPeriod(15).setMultiplier(1.5).build();
    Strategy strategy = factory.createStrategy(barSeries, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }

  @Test
  public void getDefaultParameters_returnsValidParameters() {
    LinearRegressionChannelsParameters params = factory.getDefaultParameters();
    assertThat(params.getPeriod()).isEqualTo(20);
    assertThat(params.getMultiplier()).isEqualTo(2.0);
  }
}
