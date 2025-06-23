package com.verlumen.tradestream.strategies.priceoscillatorsignal;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.PriceOscillatorSignalParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;

public final class PriceOscillatorSignalStrategyFactoryTest {

  private final PriceOscillatorSignalStrategyFactory factory =
      new PriceOscillatorSignalStrategyFactory();

  @Test
  public void getDefaultParameters_returnsValidParameters() {
    PriceOscillatorSignalParameters parameters = factory.getDefaultParameters();

    assertThat(parameters.getFastPeriod()).isEqualTo(10);
    assertThat(parameters.getSlowPeriod()).isEqualTo(20);
    assertThat(parameters.getSignalPeriod()).isEqualTo(9);
  }

  @Test
  public void createStrategy_returnsValidStrategy() {
    // Create test data
    BarSeries series = createTestBarSeries();
    PriceOscillatorSignalParameters parameters =
        PriceOscillatorSignalParameters.newBuilder()
            .setFastPeriod(5)
            .setSlowPeriod(10)
            .setSignalPeriod(3)
            .build();

    Strategy strategy = factory.createStrategy(series, parameters);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).isEqualTo("Price Oscillator Signal");

    Rule entryRule = strategy.getEntryRule();
    Rule exitRule = strategy.getExitRule();

    assertThat(entryRule).isNotNull();
    assertThat(exitRule).isNotNull();
  }

  @Test
  public void createStrategy_withValidParameters_createsStrategy() {
    BarSeries series = createTestBarSeries();
    PriceOscillatorSignalParameters parameters =
        PriceOscillatorSignalParameters.newBuilder()
            .setFastPeriod(5)
            .setSlowPeriod(15)
            .setSignalPeriod(3)
            .build();

    Strategy strategy = factory.createStrategy(series, parameters);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).isEqualTo("Price Oscillator Signal");
  }

  private BarSeries createTestBarSeries() {
    BaseBarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    Duration duration = Duration.ofMinutes(1);

    // Add some test bars
    for (int i = 0; i < 50; i++) {
      double price = 100.0 + i * 0.1;
      series.addBar(
          new BaseBar(
              duration, now.plusMinutes(i), price, price + 1.0, price - 0.5, price + 0.2, 1000.0));
    }

    return series;
  }
}
