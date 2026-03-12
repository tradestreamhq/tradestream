package com.verlumen.tradestream.strategies.rainbowoscillator;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.configurable.ConfigurableParamConfig;
import com.verlumen.tradestream.strategies.configurable.ConfigurableStrategyFactory;
import com.verlumen.tradestream.strategies.configurable.StrategyConfig;
import com.verlumen.tradestream.strategies.configurable.StrategyConfigLoader;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;
import org.ta4j.core.num.DecimalNum;

@RunWith(JUnit4.class)
public class RainbowOscillatorConfigTest {
  private StrategyConfig config;
  private ConfigurableStrategyFactory factory;
  private ConfigurableParamConfig paramConfig;
  private BaseBarSeries series;

  @Before
  public void setUp() throws Exception {
    config = StrategyConfigLoader.loadResource("strategies/rainbow_oscillator.yaml");
    factory = new ConfigurableStrategyFactory(config);
    paramConfig = new ConfigurableParamConfig(config);

    series = new BaseBarSeriesBuilder().build();
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 100; i++) {
      double price = 100 + Math.sin(i * 0.1) * 20;
      series.addBar(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i).toInstant().minus(Duration.ofMinutes(1)),
              now.plusMinutes(i).toInstant(),
              DecimalNum.valueOf(price),
              DecimalNum.valueOf(price + 2),
              DecimalNum.valueOf(price - 2),
              DecimalNum.valueOf(price),
              DecimalNum.valueOf(1000.0),
              DecimalNum.valueOf(0),
              0));
    }
  }

  @Test
  public void createStrategy_returnsValidStrategy() throws Exception {
    Strategy strategy = factory.createStrategy(series, factory.getDefaultParameters());
    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).isEqualTo("RAINBOW_OSCILLATOR");
  }

  @Test
  public void strategy_canEvaluateSignals() throws Exception {
    Strategy strategy = factory.createStrategy(series, factory.getDefaultParameters());
    for (int i = 50; i < series.getBarCount(); i++) {
      strategy.shouldEnter(i);
      strategy.shouldExit(i);
    }
  }

  @Test
  public void chromosomeSpecs_isEmpty_forFixedPeriods() {
    ImmutableList<ChromosomeSpec<?>> specs = paramConfig.getChromosomeSpecs();
    assertThat(specs).isEmpty();
  }
}
