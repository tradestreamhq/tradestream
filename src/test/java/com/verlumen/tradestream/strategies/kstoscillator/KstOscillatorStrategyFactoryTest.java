package com.verlumen.tradestream.strategies.kstoscillator;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.KstOscillatorParameters;
import java.time.Duration;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class KstOscillatorStrategyFactoryTest {

  private KstOscillatorStrategyFactory factory;
  private BarSeries barSeries;

  @Before
  public void setUp() {
    factory = new KstOscillatorStrategyFactory();
    List<Bar> bars = new ArrayList<>();
    ZonedDateTime now = ZonedDateTime.now(ZoneId.of("UTC"));
    for (int i = 0; i < 100; i++) {
      bars.add(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i),
              100.0 + i,
              101.0 + i,
              99.0 + i,
              100.0 + i,
              1000.0));
    }
    barSeries = new BaseBarSeries(bars);
  }

  @Test
  public void createStrategy_withDefaultParameters_returnsStrategy() {
    KstOscillatorParameters params = factory.getDefaultParameters();
    Strategy strategy = factory.createStrategy(barSeries, params);
    assertThat(strategy).isNotNull();
  }
}
