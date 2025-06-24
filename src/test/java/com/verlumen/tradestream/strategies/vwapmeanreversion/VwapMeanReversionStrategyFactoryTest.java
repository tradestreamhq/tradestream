package com.verlumen.tradestream.strategies.vwapmeanreversion;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.VwapMeanReversionParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class VwapMeanReversionStrategyFactoryTest {

  private final VwapMeanReversionStrategyFactory factory = new VwapMeanReversionStrategyFactory();

  @Test
  public void getDefaultParameters_returnsValidParameters() {
    VwapMeanReversionParameters parameters = factory.getDefaultParameters();

    assertThat(parameters.getVwapPeriod()).isEqualTo(20);
    assertThat(parameters.getMovingAveragePeriod()).isEqualTo(20);
    assertThat(parameters.getDeviationMultiplier()).isEqualTo(2.0);
  }

  @Test
  public void createStrategy_returnsNonNullStrategy() {
    BarSeries series = createTestBarSeries();
    VwapMeanReversionParameters parameters = factory.getDefaultParameters();

    Strategy strategy = factory.createStrategy(series, parameters);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).isEqualTo("VWAP_MEAN_REVERSION");
  }

  @Test
  public void createStrategy_returnsStrategyWithNonNullRules() {
    BarSeries series = createTestBarSeries();
    VwapMeanReversionParameters parameters = factory.getDefaultParameters();

    Strategy strategy = factory.createStrategy(series, parameters);

    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }

  @Test
  public void createStrategy_withCustomParameters_returnsValidStrategy() {
    BarSeries series = createTestBarSeries();
    VwapMeanReversionParameters parameters =
        VwapMeanReversionParameters.newBuilder()
            .setVwapPeriod(15)
            .setMovingAveragePeriod(25)
            .setDeviationMultiplier(1.5)
            .build();

    Strategy strategy = factory.createStrategy(series, parameters);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).isEqualTo("VWAP_MEAN_REVERSION");
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }

  @Test
  public void createStrategy_withMinimalBarSeries_returnsValidStrategy() {
    // Create a minimal bar series with just enough data
    BarSeries series = createMinimalBarSeries();
    VwapMeanReversionParameters parameters = factory.getDefaultParameters();

    Strategy strategy = factory.createStrategy(series, parameters);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }

  private BarSeries createTestBarSeries() {
    BarSeries series = new BaseBarSeries();

    // Add test data with varying prices and volumes
    for (int i = 0; i < 50; i++) {
      double open = 100.0 + i * 0.1;
      double high = open + 1.0;
      double low = open - 1.0;
      double close = open + (Math.random() - 0.5) * 2.0;
      double volume = 1000.0 + Math.random() * 500.0;

      Bar bar =
          new BaseBar(
              Duration.ofMinutes(1),
              ZonedDateTime.now().plusMinutes(i),
              open,
              high,
              low,
              close,
              volume);

      series.addBar(bar);
    }

    return series;
  }

  private BarSeries createMinimalBarSeries() {
    BarSeries series = new BaseBarSeries();

    // Add minimal data - just enough for indicators to work
    for (int i = 0; i < 25; i++) {
      double price = 100.0 + Math.sin(i * 0.1) * 5.0;
      double volume = 1000.0;

      Bar bar =
          new BaseBar(
              Duration.ofMinutes(1),
              ZonedDateTime.now().plusMinutes(i),
              price,
              price + 0.5,
              price - 0.5,
              price,
              volume);

      series.addBar(bar);
    }

    return series;
  }
}
