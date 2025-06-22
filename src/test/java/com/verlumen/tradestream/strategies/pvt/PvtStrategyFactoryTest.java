package com.verlumen.tradestream.strategies.pvt;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.PvtParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;
import org.junit.Test;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.Strategy;
import org.ta4j.core.num.DecimalNum;

public final class PvtStrategyFactoryTest {

  private final PvtStrategyFactory factory = new PvtStrategyFactory();

  @Test
  public void getDefaultParameters_returnsExpectedParameters() {
    PvtParameters parameters = factory.getDefaultParameters();

    assertThat(parameters.getPeriod()).isEqualTo(20);
  }

  @Test
  public void createStrategy_returnsValidStrategy() {
    BarSeries series = createTestBarSeries();
    PvtParameters parameters = PvtParameters.newBuilder().setPeriod(15).build();

    Strategy strategy = factory.createStrategy(series, parameters);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).isEqualTo("PVT");
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
    assertThat(strategy.getUnstableBars()).isEqualTo(15);
  }

  @Test
  public void createStrategy_withDefaultParameters_returnsValidStrategy() {
    BarSeries series = createTestBarSeries();
    PvtParameters parameters = factory.getDefaultParameters();

    Strategy strategy = factory.createStrategy(series, parameters);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).isEqualTo("PVT");
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
    assertThat(strategy.getUnstableBars()).isEqualTo(20);
  }

  private BarSeries createTestBarSeries() {
    List<Bar> bars = new ArrayList<>();
    ZonedDateTime now = ZonedDateTime.now();

    // Create 50 bars with varying prices and volumes
    for (int i = 0; i < 50; i++) {
      double open = 100.0 + i * 0.5;
      double high = open + 1.0;
      double low = open - 0.5;
      double close = open + (i % 2 == 0 ? 0.2 : -0.3); // Alternating price movements
      double volume = 1000.0 + i * 10.0;

      bars.add(
          new BaseBar(
              Duration.ofDays(1),
              now.plusDays(i),
              DecimalNum.valueOf(open),
              DecimalNum.valueOf(high),
              DecimalNum.valueOf(low),
              DecimalNum.valueOf(close),
              DecimalNum.valueOf(volume),
              DecimalNum.valueOf(0)));
    }

    return new org.ta4j.core.BaseBarSeries("test", bars);
  }
}
