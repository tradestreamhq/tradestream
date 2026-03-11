package com.verlumen.tradestream.strategies.doubleemacrossover;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.ConfigurableStrategyParameters;
import com.verlumen.tradestream.strategies.configurable.ConfigurableParamConfig;
import com.verlumen.tradestream.strategies.configurable.ConfigurableStrategyFactory;
import com.verlumen.tradestream.strategies.configurable.StrategyConfig;
import com.verlumen.tradestream.strategies.configurable.StrategyConfigLoader;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

@RunWith(JUnit4.class)
public class DoubleEmaCrossoverConfigTest {
  private StrategyConfig config;
  private ConfigurableStrategyFactory factory;
  private ConfigurableParamConfig paramConfig;
  private BaseBarSeries series;

  @Before
  public void setUp() throws Exception {
    config = StrategyConfigLoader.loadResource("strategies/double_ema_crossover.yaml");
    factory = new ConfigurableStrategyFactory(config);
    paramConfig = new ConfigurableParamConfig(config);
    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 1200; i++) {
      double price = 100 + Math.sin(i * 0.1) * 20 + Math.cos(i * 0.03) * 10;
      series.addBar(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i),
              price,
              price + 2,
              price - 2,
              price,
              1000.0));
    }
  }

  @Test
  public void createStrategy_returnsValidStrategy() throws Exception {
    Strategy strategy = factory.createStrategy(series, factory.getDefaultParameters());
    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).isEqualTo("DOUBLE_EMA_CROSSOVER");
  }

  @Test
  public void strategy_canEvaluateSignals_over1000Candles() throws Exception {
    Strategy strategy = factory.createStrategy(series, factory.getDefaultParameters());
    int entrySignals = 0;
    int exitSignals = 0;
    for (int i = 50; i < series.getBarCount(); i++) {
      if (strategy.shouldEnter(i)) {
        entrySignals++;
      }
      if (strategy.shouldExit(i)) {
        exitSignals++;
      }
    }
    assertThat(entrySignals).isGreaterThan(0);
    assertThat(exitSignals).isGreaterThan(0);
  }

  @Test
  public void config_hasCorrectIndicators() {
    assertThat(config.getIndicators()).hasSize(2);
    assertThat(config.getIndicators().get(0).getId()).isEqualTo("shortEma");
    assertThat(config.getIndicators().get(0).getType()).isEqualTo("EMA");
    assertThat(config.getIndicators().get(1).getId()).isEqualTo("longEma");
    assertThat(config.getIndicators().get(1).getType()).isEqualTo("EMA");
  }

  @Test
  public void config_hasCorrectEntryExitConditions() {
    assertThat(config.getEntryConditions()).hasSize(1);
    assertThat(config.getEntryConditions().get(0).getType()).isEqualTo("CROSSED_UP");
    assertThat(config.getExitConditions()).hasSize(1);
    assertThat(config.getExitConditions().get(0).getType()).isEqualTo("CROSSED_DOWN");
  }

  @Test
  public void chromosomeSpecs_matchParameterCount() {
    ImmutableList<ChromosomeSpec<?>> specs = paramConfig.getChromosomeSpecs();
    assertThat(specs).hasSize(2);
  }

  @Test
  public void createParameters_fromChromosomes_succeeds() throws Exception {
    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(IntegerChromosome.of(5, 20, 10), IntegerChromosome.of(20, 50, 30));
    Any packed = paramConfig.createParameters(chromosomes);
    assertThat(packed.is(ConfigurableStrategyParameters.class)).isTrue();
  }
}
