package com.verlumen.tradestream.strategies.rainbowoscillator;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.RainbowOscillatorParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;
import org.ta4j.core.num.DecimalNum;

public final class RainbowOscillatorStrategyFactoryTest {
  private final RainbowOscillatorStrategyFactory factory = new RainbowOscillatorStrategyFactory();

  @Test
  public void getDefaultParameters_returnsValidParameters() {
    // Act
    RainbowOscillatorParameters params = factory.getDefaultParameters();

    // Assert
    assertThat(params).isNotNull();
    assertThat(params.getPeriodsCount()).isEqualTo(3);
    assertThat(params.getPeriods(0)).isEqualTo(10);
    assertThat(params.getPeriods(1)).isEqualTo(20);
    assertThat(params.getPeriods(2)).isEqualTo(50);
  }

  @Test
  public void createStrategy_returnsValidStrategy() {
    // Arrange
    BarSeries series = createTestBarSeries();
    RainbowOscillatorParameters parameters = factory.getDefaultParameters();

    // Act
    Strategy strategy = factory.createStrategy(series, parameters);

    // Assert
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }

  private BarSeries createTestBarSeries() {
    BaseBarSeries series = new BaseBarSeriesBuilder().build();
    ZonedDateTime now = ZonedDateTime.now();

    for (int i = 1; i <= 20; i++) {
      series.addBar(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i - 1).toInstant(),
              now.plusMinutes(i).toInstant(),
              DecimalNum.valueOf(100.0 + i),
              DecimalNum.valueOf(105.0 + i),
              DecimalNum.valueOf(95.0 + i),
              DecimalNum.valueOf(102.0 + i),
              DecimalNum.valueOf(1000.0),
              DecimalNum.valueOf(0),
              0));
    }

    return series;
  }
}
