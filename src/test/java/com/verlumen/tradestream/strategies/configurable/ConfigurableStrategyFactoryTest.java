package com.verlumen.tradestream.strategies.configurable;

import static org.junit.Assert.*;

import com.verlumen.tradestream.strategies.ConfigurableStrategyParameters;
import java.util.List;
import java.util.Map;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;

/**
 * Tests for ConfigurableStrategyFactory verifying that config-based strategies produce valid Ta4j
 * strategies.
 */
public class ConfigurableStrategyFactoryTest {

  private BarSeries testSeries;

  @Before
  public void setUp() {
    // Create a test bar series with some sample data
    testSeries = new BaseBarSeriesBuilder().withName("test").build();

    // Add 100 bars of synthetic data
    for (int i = 0; i < 100; i++) {
      double price = 100 + Math.sin(i * 0.1) * 10;
      testSeries.addBar(
          java.time.ZonedDateTime.now().plusMinutes(i),
          price - 1, // open
          price + 2, // high
          price - 2, // low
          price, // close
          1000 + i // volume
          );
    }
  }

  @Test
  public void testSmaEmaCrossoverConfig() throws Exception {
    // Create a config equivalent to SmaEmaCrossover
    StrategyConfig config =
        StrategyConfig.builder()
            .name("SMA_EMA_CROSSOVER_CONFIG")
            .description("SMA crosses EMA - config based")
            .complexity("SIMPLE")
            .indicators(
                List.of(
                    IndicatorConfig.builder()
                        .id("sma")
                        .type("SMA")
                        .input("close")
                        .params(Map.of("period", "${smaPeriod}"))
                        .build(),
                    IndicatorConfig.builder()
                        .id("ema")
                        .type("EMA")
                        .input("close")
                        .params(Map.of("period", "${emaPeriod}"))
                        .build()))
            .entryConditions(
                List.of(
                    ConditionConfig.builder()
                        .type("CROSSED_UP")
                        .indicator("sma")
                        .params(Map.of("crosses", "ema"))
                        .build()))
            .exitConditions(
                List.of(
                    ConditionConfig.builder()
                        .type("CROSSED_DOWN")
                        .indicator("sma")
                        .params(Map.of("crosses", "ema"))
                        .build()))
            .parameters(
                List.of(
                    ParameterDefinition.builder()
                        .name("smaPeriod")
                        .type(ParameterType.INTEGER)
                        .min(5)
                        .max(50)
                        .defaultValue(20)
                        .build(),
                    ParameterDefinition.builder()
                        .name("emaPeriod")
                        .type(ParameterType.INTEGER)
                        .min(5)
                        .max(50)
                        .defaultValue(10)
                        .build()))
            .build();

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);

    // Create strategy with default parameters
    ConfigurableStrategyParameters params = factory.getDefaultParameters();
    Strategy strategy = factory.createStrategy(testSeries, params);

    assertNotNull("Strategy should not be null", strategy);
    assertEquals(
        "Strategy name should match config", "SMA_EMA_CROSSOVER_CONFIG", strategy.getName());

    // Verify the strategy can evaluate entry/exit conditions
    // After sufficient bars, we should be able to check signals
    // Using bar index 50 as a safe starting point after indicator warmup
    for (int i = 50; i < testSeries.getBarCount(); i++) {
      // These should not throw exceptions
      strategy.shouldEnter(i);
      strategy.shouldExit(i);
    }
  }

  @Test
  public void testRsiBasedConfig() throws Exception {
    // Create a config using RSI
    StrategyConfig config =
        StrategyConfig.builder()
            .name("RSI_OVERSOLD_OVERBOUGHT")
            .description("Buy when RSI oversold, sell when overbought")
            .complexity("SIMPLE")
            .indicators(
                List.of(
                    IndicatorConfig.builder()
                        .id("rsi")
                        .type("RSI")
                        .input("close")
                        .params(Map.of("period", "${rsiPeriod}"))
                        .build()))
            .entryConditions(
                List.of(
                    ConditionConfig.builder()
                        .type("CROSSES_ABOVE")
                        .indicator("rsi")
                        .params(Map.of("value", 30.0))
                        .build()))
            .exitConditions(
                List.of(
                    ConditionConfig.builder()
                        .type("CROSSES_BELOW")
                        .indicator("rsi")
                        .params(Map.of("value", 70.0))
                        .build()))
            .parameters(
                List.of(
                    ParameterDefinition.builder()
                        .name("rsiPeriod")
                        .type(ParameterType.INTEGER)
                        .min(7)
                        .max(21)
                        .defaultValue(14)
                        .build()))
            .build();

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params = factory.getDefaultParameters();
    Strategy strategy = factory.createStrategy(testSeries, params);

    assertNotNull("Strategy should not be null", strategy);
    assertEquals("RSI_OVERSOLD_OVERBOUGHT", strategy.getName());
  }

  @Test
  public void testMacdCrossoverConfig() throws Exception {
    // Create a MACD crossover config
    StrategyConfig config =
        StrategyConfig.builder()
            .name("MACD_CROSSOVER_CONFIG")
            .description("MACD crosses signal line")
            .complexity("MEDIUM")
            .indicators(
                List.of(
                    IndicatorConfig.builder()
                        .id("macd")
                        .type("MACD")
                        .input("close")
                        .params(
                            Map.of(
                                "shortPeriod", "${shortPeriod}",
                                "longPeriod", "${longPeriod}"))
                        .build(),
                    IndicatorConfig.builder()
                        .id("signal")
                        .type("EMA")
                        .input("macd")
                        .params(Map.of("period", "${signalPeriod}"))
                        .build()))
            .entryConditions(
                List.of(
                    ConditionConfig.builder()
                        .type("CROSSED_UP")
                        .indicator("macd")
                        .params(Map.of("crosses", "signal"))
                        .build()))
            .exitConditions(
                List.of(
                    ConditionConfig.builder()
                        .type("CROSSED_DOWN")
                        .indicator("macd")
                        .params(Map.of("crosses", "signal"))
                        .build()))
            .parameters(
                List.of(
                    ParameterDefinition.builder()
                        .name("shortPeriod")
                        .type(ParameterType.INTEGER)
                        .min(8)
                        .max(16)
                        .defaultValue(12)
                        .build(),
                    ParameterDefinition.builder()
                        .name("longPeriod")
                        .type(ParameterType.INTEGER)
                        .min(20)
                        .max(32)
                        .defaultValue(26)
                        .build(),
                    ParameterDefinition.builder()
                        .name("signalPeriod")
                        .type(ParameterType.INTEGER)
                        .min(5)
                        .max(12)
                        .defaultValue(9)
                        .build()))
            .build();

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params = factory.getDefaultParameters();
    Strategy strategy = factory.createStrategy(testSeries, params);

    assertNotNull("Strategy should not be null", strategy);
    assertEquals("MACD_CROSSOVER_CONFIG", strategy.getName());
  }

  @Test
  public void testCustomParameters() throws Exception {
    StrategyConfig config =
        StrategyConfig.builder()
            .name("CUSTOM_PARAM_TEST")
            .description("Test custom parameters")
            .complexity("SIMPLE")
            .indicators(
                List.of(
                    IndicatorConfig.builder()
                        .id("sma")
                        .type("SMA")
                        .input("close")
                        .params(Map.of("period", "${period}"))
                        .build()))
            .entryConditions(
                List.of(
                    ConditionConfig.builder()
                        .type("ABOVE")
                        .indicator("close")
                        .params(Map.of("other", "sma"))
                        .build()))
            .exitConditions(
                List.of(
                    ConditionConfig.builder()
                        .type("BELOW")
                        .indicator("close")
                        .params(Map.of("other", "sma"))
                        .build()))
            .parameters(
                List.of(
                    ParameterDefinition.builder()
                        .name("period")
                        .type(ParameterType.INTEGER)
                        .min(5)
                        .max(100)
                        .defaultValue(20)
                        .build()))
            .build();

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);

    // Test with custom parameters
    ConfigurableStrategyParameters customParams =
        ConfigurableStrategyParameters.newBuilder().putIntValues("period", 50).build();

    Strategy strategy = factory.createStrategy(testSeries, customParams);
    assertNotNull("Strategy with custom params should not be null", strategy);
  }

  @Test
  public void testDefaultParameters() {
    StrategyConfig config =
        StrategyConfig.builder()
            .name("DEFAULT_PARAMS_TEST")
            .parameters(
                List.of(
                    ParameterDefinition.builder()
                        .name("intParam")
                        .type(ParameterType.INTEGER)
                        .min(1)
                        .max(100)
                        .defaultValue(42)
                        .build(),
                    ParameterDefinition.builder()
                        .name("doubleParam")
                        .type(ParameterType.DOUBLE)
                        .min(0.0)
                        .max(1.0)
                        .defaultValue(0.5)
                        .build()))
            .indicators(List.of())
            .entryConditions(List.of())
            .exitConditions(List.of())
            .build();

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters defaults = factory.getDefaultParameters();

    assertEquals(42, defaults.getIntValuesOrDefault("intParam", 0));
    assertEquals(0.5, defaults.getDoubleValuesOrDefault("doubleParam", 0.0), 0.001);
  }
}
