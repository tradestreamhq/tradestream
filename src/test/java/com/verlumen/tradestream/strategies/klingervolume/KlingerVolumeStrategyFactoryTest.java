package com.verlumen.tradestream.strategies.klingervolume;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.KlingerVolumeParameters;

import org.junit.Test;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.Strategy;
import org.ta4j.core.num.DecimalNum;

import java.time.Duration;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;

public final class KlingerVolumeStrategyFactoryTest {

  private final KlingerVolumeStrategyFactory factory = new KlingerVolumeStrategyFactory();

  @Test
  public void getDefaultParameters_returnsExpectedParameters() {
    KlingerVolumeParameters parameters = factory.getDefaultParameters();

    assertThat(parameters.getShortPeriod()).isEqualTo(10);
    assertThat(parameters.getLongPeriod()).isEqualTo(35);
    assertThat(parameters.getSignalPeriod()).isEqualTo(10);
  }

  @Test
  public void createStrategy_returnsValidStrategy() {
    BarSeries series = createTestBarSeries();

    KlingerVolumeParameters parameters = KlingerVolumeParameters.newBuilder()
        .setShortPeriod(5)
        .setLongPeriod(10)
        .setSignalPeriod(5)
        .build();
    
    Strategy strategy = factory.createStrategy(series, parameters);
    
    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).isEqualTo("KLINGER_VOLUME");
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
    assertThat(strategy.getUnstableBars()).isEqualTo(10);
  }

  @Test
  public void createStrategy_withDefaultParameters_returnsValidStrategy() {
    BarSeries series = createTestBarSeries();
    KlingerVolumeParameters parameters = factory.getDefaultParameters();
    
    Strategy strategy = factory.createStrategy(series, parameters);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).isEqualTo("KLINGER_VOLUME");
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
    assertThat(strategy.getUnstableBars()).isEqualTo(35);
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
      
      bars.add(new BaseBar(
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
