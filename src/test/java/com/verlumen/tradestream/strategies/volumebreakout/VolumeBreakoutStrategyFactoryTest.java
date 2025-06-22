package com.verlumen.tradestream.strategies.volumebreakout;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.VolumeBreakoutParameters;
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

public final class VolumeBreakoutStrategyFactoryTest {

  private final VolumeBreakoutStrategyFactory factory = new VolumeBreakoutStrategyFactory();

  @Test
  public void getDefaultParameters_returnsExpectedParameters() {
    VolumeBreakoutParameters parameters = factory.getDefaultParameters();

    assertThat(parameters.getVolumeMultiplier()).isEqualTo(2.0);
  }

  @Test
  public void createStrategy_returnsValidStrategy() {
    BarSeries series = createTestBarSeries();
    VolumeBreakoutParameters parameters =
        VolumeBreakoutParameters.newBuilder().setVolumeMultiplier(2.5).build();

    Strategy strategy = factory.createStrategy(series, parameters);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).isEqualTo("VOLUME_BREAKOUT");
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
    assertThat(strategy.getUnstableBars()).isEqualTo(20);
  }

  @Test
  public void createStrategy_withDefaultParameters_returnsValidStrategy() {
    BarSeries series = createTestBarSeries();
    VolumeBreakoutParameters parameters = factory.getDefaultParameters();

    Strategy strategy = factory.createStrategy(series, parameters);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).isEqualTo("VOLUME_BREAKOUT");
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
    assertThat(strategy.getUnstableBars()).isEqualTo(20);
  }

  private BarSeries createTestBarSeries() {
    List<Bar> bars = new ArrayList<>();
    ZonedDateTime now = ZonedDateTime.now();

    // Create 50 bars with increasing prices and volumes
    for (int i = 0; i < 50; i++) {
      double open = 100.0 + i * 0.5;
      double high = open + 1.0;
      double low = open - 0.5;
      double close = open + 0.2;
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
