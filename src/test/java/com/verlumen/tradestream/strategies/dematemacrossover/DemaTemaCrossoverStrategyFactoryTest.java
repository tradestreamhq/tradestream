package com.verlumen.tradestream.strategies.dematemacrossover;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.DemaTemaCrossoverParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class DemaTemaCrossoverStrategyFactoryTest {
  private final DemaTemaCrossoverStrategyFactory factory = new DemaTemaCrossoverStrategyFactory();

  @Test
  public void getDefaultParameters_returnsValidParameters() {
    // Act
    DemaTemaCrossoverParameters params = factory.getDefaultParameters();

    // Assert
    assertThat(params.getDemaPeriod()).isEqualTo(12);
    assertThat(params.getTemaPeriod()).isEqualTo(26);
  }

  @Test
  public void createStrategy_returnsValidStrategy() throws InvalidProtocolBufferException {
    // Arrange
    BarSeries series = createTestBarSeries();
    DemaTemaCrossoverParameters params = factory.getDefaultParameters();

    // Act
    Strategy strategy = factory.createStrategy(series, params);

    // Assert
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }

  @Test(expected = IllegalArgumentException.class)
  public void createStrategy_withInvalidDemaPeriod_throwsException()
      throws InvalidProtocolBufferException {
    // Arrange
    BarSeries series = createTestBarSeries();
    DemaTemaCrossoverParameters params =
        DemaTemaCrossoverParameters.newBuilder().setDemaPeriod(0).setTemaPeriod(26).build();

    // Act & Assert
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void createStrategy_withInvalidTemaPeriod_throwsException()
      throws InvalidProtocolBufferException {
    // Arrange
    BarSeries series = createTestBarSeries();
    DemaTemaCrossoverParameters params =
        DemaTemaCrossoverParameters.newBuilder().setDemaPeriod(12).setTemaPeriod(0).build();

    // Act & Assert
    factory.createStrategy(series, params);
  }

  private BarSeries createTestBarSeries() {
    BarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Add some test data
    for (int i = 0; i < 100; i++) {
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
