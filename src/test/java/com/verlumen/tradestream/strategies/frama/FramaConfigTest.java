package com.verlumen.tradestream.strategies.frama;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.ConfigurableStrategyParameters;
import com.verlumen.tradestream.strategies.configurable.ConfigurableParamConfig;
import com.verlumen.tradestream.strategies.configurable.ConfigurableStrategyFactory;
import com.verlumen.tradestream.strategies.configurable.StrategyConfig;
import com.verlumen.tradestream.strategies.configurable.StrategyConfigLoader;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;

@RunWith(JUnit4.class)
public class FramaConfigTest {
  private StrategyConfig config;
  private ConfigurableStrategyFactory factory;
  private ConfigurableParamConfig paramConfig;
  private BarSeries series;

  @Before
  public void setUp() throws Exception {
    config = StrategyConfigLoader.loadResource("strategies/frama.yaml");
    factory = new ConfigurableStrategyFactory(config);
    paramConfig = new ConfigurableParamConfig(config);

    series = new BaseBarSeriesBuilder().withName("frama-test").build();
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 100; i++) {
      double price = 100 + Math.sin(i * 0.1) * 20;
      double high = price + 2;
      double low = price - 2;
      double open = price - 0.5;
      double close = price;
      long volume = 1000;
      series.addBar(now.plusMinutes(i), open, high, low, close, volume);
    }
  }

  @Test
  public void createStrategy_returnsValidStrategy() throws Exception {
    Strategy strategy = factory.createStrategy(series, factory.getDefaultParameters());
    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).isEqualTo("FRAMA");
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
  public void chromosomeSpecs_matchParameterCount() {
    ImmutableList<ChromosomeSpec<?>> specs = paramConfig.getChromosomeSpecs();
    assertThat(specs).hasSize(3);
  }

  @Test
  public void createParameters_fromChromosomes_succeeds() throws Exception {
    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(
            DoubleChromosome.of(0.1, 2.0),
            IntegerChromosome.of(5, 50),
            DoubleChromosome.of(0.1, 1.0));
    Any packed = paramConfig.createParameters(chromosomes);
    assertThat(packed.is(ConfigurableStrategyParameters.class)).isTrue();
  }
}
