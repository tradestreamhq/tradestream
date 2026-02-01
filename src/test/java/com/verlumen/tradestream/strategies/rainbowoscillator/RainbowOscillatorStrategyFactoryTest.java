package com.verlumen.tradestream.strategies.rainbowoscillator;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.RainbowOscillatorParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

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
  public void createStrategy_returnsValidStrategy() throws Exception {
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
    BaseBarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    for (int i = 0; i < 20; i++) {
      series.addBar(
          BaseBar.builder()
              .endTime(now.plusMinutes(i))
              .timePeriod(Duration.ofMinutes(1))
              .openPrice(series.numOf(100.0 + i))
              .highPrice(series.numOf(105.0 + i))
              .lowPrice(series.numOf(95.0 + i))
              .closePrice(series.numOf(102.0 + i))
              .volume(series.numOf(1000.0))
              .build());
    }

    return series;
  }
}
