package com.verlumen.tradestream.strategies.heikenashi;

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
public class HeikenAshiConfigTest {
  private StrategyConfig config;
  private ConfigurableStrategyFactory factory;
  private ConfigurableParamConfig paramConfig;
  private BaseBarSeries series;

  @Before
  public void setUp() throws Exception {
    config = StrategyConfigLoader.loadResource("strategies/heiken_ashi.yaml");
    factory = new ConfigurableStrategyFactory(config);
    paramConfig = new ConfigurableParamConfig(config);

    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 100; i++) {
      double price = 100 + Math.sin(i * 0.1) * 20;
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
  public void createStrategy_returnsValidStrategy() {
    Strategy strategy = factory.createStrategy(series, factory.getDefaultParameters());
    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).isEqualTo("HEIKEN_ASHI");
  }

  @Test
  public void strategy_canEvaluateSignals() {
    Strategy strategy = factory.createStrategy(series, factory.getDefaultParameters());
    for (int i = 50; i < series.getBarCount(); i++) {
      strategy.shouldEnter(i);
      strategy.shouldExit(i);
    }
  }

  @Test
  public void defaultParameters_areWithinBounds() {
    ConfigurableStrategyParameters params = factory.getDefaultParameters();
    assertThat(params.getIntValuesOrDefault("period", 0))
        .isIn(com.google.common.collect.Range.closed(5, 20));
  }

  @Test
  public void chromosomeSpecs_matchParameterCount() {
    ImmutableList<ChromosomeSpec<?>> specs = paramConfig.getChromosomeSpecs();
    assertThat(specs).hasSize(1);
  }

  @Test
  public void createParameters_fromChromosomes_succeeds() throws Exception {
    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(IntegerChromosome.of(5, 20, 10));
    Any packed = paramConfig.createParameters(chromosomes);
    assertThat(packed.is(ConfigurableStrategyParameters.class)).isTrue();
  }
}
