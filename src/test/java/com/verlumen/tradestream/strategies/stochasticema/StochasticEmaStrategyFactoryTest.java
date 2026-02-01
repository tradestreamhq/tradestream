package com.verlumen.tradestream.strategies.stochasticema;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.Any;
import com.verlumen.tradestream.strategies.StochasticEmaParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.Strategy;

public class StochasticEmaStrategyFactoryTest {

  private final StochasticEmaStrategyFactory factory = new StochasticEmaStrategyFactory();

  @Test
  public void createStrategy_returnsValidStrategy() throws Exception {
    // Arrange
    BarSeries barSeries = new org.ta4j.core.BaseBarSeries();
    barSeries.addBar(
        new BaseBar(Duration.ofDays(1), ZonedDateTime.now(), 100.0, 110.0, 90.0, 105.0, 1000.0));
    barSeries.addBar(
        new BaseBar(
            Duration.ofDays(1),
            ZonedDateTime.now().plusDays(1),
            105.0,
            115.0,
            95.0,
            110.0,
            1100.0));
    barSeries.addBar(
        new BaseBar(
            Duration.ofDays(1),
            ZonedDateTime.now().plusDays(2),
            110.0,
            120.0,
            100.0,
            115.0,
            1200.0));

    StochasticEmaParameters params =
        StochasticEmaParameters.newBuilder()
            .setStochasticKPeriod(14)
            .setStochasticDPeriod(3)
            .setEmaPeriod(14)
            .setOverboughtThreshold(80)
            .setOversoldThreshold(20)
            .build();

    Any packedParams = Any.pack(params);

    // Act
    Strategy strategy = factory.createStrategy(barSeries, packedParams);

    // Assert
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }

  @Test
  public void createStrategy_withDirectParameters_returnsValidStrategy() {
    // Arrange
    BarSeries barSeries = new org.ta4j.core.BaseBarSeries();
    barSeries.addBar(
        new BaseBar(Duration.ofDays(1), ZonedDateTime.now(), 100.0, 110.0, 90.0, 105.0, 1000.0));
    barSeries.addBar(
        new BaseBar(
            Duration.ofDays(1),
            ZonedDateTime.now().plusDays(1),
            105.0,
            115.0,
            95.0,
            110.0,
            1100.0));
    barSeries.addBar(
        new BaseBar(
            Duration.ofDays(1),
            ZonedDateTime.now().plusDays(2),
            110.0,
            120.0,
            100.0,
            115.0,
            1200.0));

    StochasticEmaParameters params =
        StochasticEmaParameters.newBuilder()
            .setStochasticKPeriod(14)
            .setStochasticDPeriod(3)
            .setEmaPeriod(14)
            .setOverboughtThreshold(80)
            .setOversoldThreshold(20)
            .build();

    // Act
    Strategy strategy = factory.createStrategy(barSeries, params);

    // Assert
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }
}
