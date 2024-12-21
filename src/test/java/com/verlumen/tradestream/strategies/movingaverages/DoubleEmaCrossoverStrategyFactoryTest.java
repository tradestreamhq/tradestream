package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.truth.Truth.assertThat;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

@RunWith(JUnit4.class)
public class DoubleEmaCrossoverStrategyFactoryTest {
  private static final BarSeries SERIES = newBarSeries();

  @Inject
  private DoubleEmaCrossoverStrategyFactory factory;

  @Before
  public void setUp() {
    Guice.createInjector().injectMembers(this);
  }

  @Test
  void createStrategy_validParameters_createsStrategy() throws InvalidProtocolBufferException {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(5).setLongEmaPeriod(10).build();

    // Act
    Strategy strategy = factory.createStrategy(SERIES, params);

    // Assert
    assertThat(strategy).isNotNull();
  }

  @Test
  void createStrategy_shortEmaPeriodZero_throwsIllegalArgumentException() {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(0).setLongEmaPeriod(10).build();

    // Act
    Throwable thrown =
        assertThrows(IllegalArgumentException.class, () -> factory.createStrategy(SERIES, params));

    // Assert
    assertThat(thrown).hasMessageThat().contains("shortEmaPeriod");
  }

  @Test
  void createStrategy_shortEmaPeriodNegative_throwsIllegalArgumentException() {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(-1).setLongEmaPeriod(10).build();

    // Act
    Throwable thrown =
        assertThrows(IllegalArgumentException.class, () -> factory.createStrategy(SERIES, params));

    // Assert
    assertThat(thrown).hasMessageThat().contains("shortEmaPeriod");
  }

  @Test
  void createStrategy_longEmaPeriodZero_throwsIllegalArgumentException() {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(5).setLongEmaPeriod(0).build();

    // Act
    Throwable thrown =
        assertThrows(IllegalArgumentException.class, () -> factory.createStrategy(SERIES, params));

    // Assert
    assertThat(thrown).hasMessageThat().contains("longEmaPeriod");
  }

  @Test
  void createStrategy_longEmaPeriodNegative_throwsIllegalArgumentException() {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(5).setLongEmaPeriod(-1).build();

    // Act
    Throwable thrown =
        assertThrows(IllegalArgumentException.class, () -> factory.createStrategy(SERIES, params));

    // Assert
    assertThat(thrown).hasMessageThat().contains("longEmaPeriod");
  }

  @Test
  void createStrategy_longEmaPeriodLessThanOrEqualToShortEmaPeriod_throwsIllegalArgumentException() {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(10).setLongEmaPeriod(10).build();

    // Act
    Throwable thrown =
        assertThrows(IllegalArgumentException.class, () -> factory.createStrategy(SERIES, params));

    // Assert
    assertThat(thrown)
        .hasMessageThat()
        .contains("longEmaPeriod must be greater than shortEmaPeriod");
  }

  @Test
  void getStrategyType_returnsDoubleEmaCrossover() {
    // Arrange (no specific arrangement needed)

    // Act
    StrategyType strategyType = factory.getStrategyType();

    // Assert
    assertThat(strategyType).isEqualTo(StrategyType.DOUBLE_EMA_CROSSOVER);
  }

  private static BarSeries newBarSeries() {
    BarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.minusMinutes(2), 10, 12, 8, 11));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.minusMinutes(1), 11, 13, 9, 12));
    return series;
  }
}
