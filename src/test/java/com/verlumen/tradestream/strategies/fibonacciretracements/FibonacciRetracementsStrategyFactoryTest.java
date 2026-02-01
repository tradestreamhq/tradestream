package com.verlumen.tradestream.strategies.fibonacciretracements;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.FibonacciRetracementsParameters;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class FibonacciRetracementsStrategyFactoryTest {

  private final FibonacciRetracementsStrategyFactory factory =
      new FibonacciRetracementsStrategyFactory();
  private final BarSeries series = new BaseBarSeries();

  @Test
  public void getDefaultParameters_returnsCorrectParameters() {
    // Act
    FibonacciRetracementsParameters result = factory.getDefaultParameters();

    // Assert
    assertThat(result).isNotNull();
    assertThat(result.getPeriod()).isEqualTo(20);
  }

  @Test
  public void createStrategy_returnsValidStrategy() throws Exception {
    // Arrange
    FibonacciRetracementsParameters parameters = factory.getDefaultParameters();

    // Act
    Strategy result = factory.createStrategy(series, parameters);

    // Assert
    assertThat(result).isNotNull();
    assertThat(result.getEntryRule()).isNotNull();
    assertThat(result.getExitRule()).isNotNull();
  }
}
