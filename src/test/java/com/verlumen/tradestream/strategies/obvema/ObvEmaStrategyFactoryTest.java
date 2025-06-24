package com.verlumen.tradestream.strategies.obvema;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.ObvEmaParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class ObvEmaStrategyFactoryTest {

  private final ObvEmaStrategyFactory factory = new ObvEmaStrategyFactory();

  @Test
  public void getDefaultParameters_returnsValidParameters() {
    ObvEmaParameters parameters = factory.getDefaultParameters();

    assertThat(parameters.getEmaPeriod()).isEqualTo(20);
  }

  @Test
  public void createStrategy_returnsNonNullStrategy() {
    // Arrange
    BarSeries series = createTestBarSeries();
    ObvEmaParameters parameters = ObvEmaParameters.newBuilder().setEmaPeriod(15).build();

    // Act
    Strategy strategy = factory.createStrategy(series, parameters);

    // Assert
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }

  @Test
  public void createStrategy_withDefaultParameters_returnsNonNullStrategy() {
    // Arrange
    BarSeries series = createTestBarSeries();

    // Act
    Strategy strategy = factory.createStrategy(series, factory.getDefaultParameters());

    // Assert
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }

  @Test
  public void createStrategy_withCustomParameters_usesCorrectEmaPeriod() {
    // Arrange
    BarSeries series = createTestBarSeries();
    ObvEmaParameters parameters = ObvEmaParameters.newBuilder().setEmaPeriod(25).build();

    // Act
    Strategy strategy = factory.createStrategy(series, parameters);

    // Assert
    assertThat(strategy).isNotNull();
    assertThat(strategy.getUnstableBars()).isEqualTo(25);
  }

  private BarSeries createTestBarSeries() {
    BaseBarSeries series = new BaseBarSeries();
    ZonedDateTime time = ZonedDateTime.now();

    // Add some test bars
    for (int i = 0; i < 50; i++) {
      double price = 100.0 + i * 0.1;
      double volume = 1000.0 + i * 10.0;
      Bar bar =
          new BaseBar(
              Duration.ofMinutes(1), time.plusMinutes(i), price, price, price, price, volume);
      series.addBar(bar);
    }

    return series;
  }
}
