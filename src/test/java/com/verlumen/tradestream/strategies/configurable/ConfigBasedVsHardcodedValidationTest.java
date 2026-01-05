package com.verlumen.tradestream.strategies.configurable;

import static org.junit.Assert.*;

import com.verlumen.tradestream.strategies.ConfigurableStrategyParameters;
import com.verlumen.tradestream.strategies.SmaEmaCrossoverParameters;
import com.verlumen.tradestream.strategies.smaemacrossover.SmaEmaCrossoverStrategyFactory;
import java.util.List;
import java.util.Map;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;

/**
 * Validation tests to ensure config-based strategies produce the same signals as their hardcoded
 * counterparts. This is critical for verifying the migration from Java classes to YAML configs.
 */
public class ConfigBasedVsHardcodedValidationTest {

  private BarSeries testSeries;

  @Before
  public void setUp() {
    // Create a test bar series with synthetic data that will generate entry/exit signals
    testSeries = new BaseBarSeriesBuilder().withName("validation-test").build();

    // Generate data with clear trends to trigger crossover signals
    // Pattern: gradual increase, then gradual decrease, repeat
    double basePrice = 100.0;
    for (int i = 0; i < 200; i++) {
      // Create oscillating price pattern
      double cycle = Math.sin(i * 0.1) * 20 + Math.sin(i * 0.05) * 10;
      double price = basePrice + cycle;
      double high = price + 2;
      double low = price - 2;
      double open = price - 0.5;
      double close = price;
      long volume = 1000 + (long) (Math.random() * 500);

      testSeries.addBar(
          java.time.ZonedDateTime.now().plusMinutes(i), open, high, low, close, volume);
    }
  }

  @Test
  public void testSmaEmaCrossoverConfigMatchesHardcoded() throws Exception {
    // Parameters to test with
    int smaPeriod = 20;
    int emaPeriod = 50;

    // Create hardcoded strategy
    SmaEmaCrossoverStrategyFactory hardcodedFactory = new SmaEmaCrossoverStrategyFactory();
    SmaEmaCrossoverParameters hardcodedParams =
        SmaEmaCrossoverParameters.newBuilder()
            .setSmaPeriod(smaPeriod)
            .setEmaPeriod(emaPeriod)
            .build();
    Strategy hardcodedStrategy = hardcodedFactory.createStrategy(testSeries, hardcodedParams);

    // Create config-based strategy matching the hardcoded one
    StrategyConfig config =
        StrategyConfig.builder()
            .name("SMA_EMA_CROSSOVER_CONFIG")
            .description("Config-based SMA/EMA crossover for validation")
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
                        .max(100)
                        .defaultValue(smaPeriod)
                        .build(),
                    ParameterDefinition.builder()
                        .name("emaPeriod")
                        .type(ParameterType.INTEGER)
                        .min(5)
                        .max(100)
                        .defaultValue(emaPeriod)
                        .build()))
            .build();

    ConfigurableStrategyFactory configFactory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters configParams =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("smaPeriod", smaPeriod)
            .putIntValues("emaPeriod", emaPeriod)
            .build();
    Strategy configStrategy = configFactory.createStrategy(testSeries, configParams);

    // Compare signals for all bars after warmup period
    int warmupPeriod = Math.max(smaPeriod, emaPeriod) + 10;
    int mismatches = 0;
    int totalChecks = 0;

    for (int i = warmupPeriod; i < testSeries.getBarCount(); i++) {
      boolean hardcodedEntry = hardcodedStrategy.shouldEnter(i);
      boolean configEntry = configStrategy.shouldEnter(i);
      boolean hardcodedExit = hardcodedStrategy.shouldExit(i);
      boolean configExit = configStrategy.shouldExit(i);

      totalChecks++;

      if (hardcodedEntry != configEntry) {
        mismatches++;
        // Uncomment for debugging:
        // System.err.printf("Entry mismatch at bar %d: hardcoded=%b, config=%b%n",
        //     i, hardcodedEntry, configEntry);
      }

      if (hardcodedExit != configExit) {
        mismatches++;
        // Uncomment for debugging:
        // System.err.printf("Exit mismatch at bar %d: hardcoded=%b, config=%b%n",
        //     i, hardcodedExit, configExit);
      }
    }

    // Assert no mismatches
    assertEquals(
        String.format(
            "Config-based strategy should match hardcoded strategy. "
                + "Found %d mismatches in %d checks",
            mismatches, totalChecks * 2),
        0,
        mismatches);

    // Ensure we actually tested something meaningful
    assertTrue("Should have tested at least 50 bars", totalChecks >= 50);
  }

  @Test
  public void testYamlLoadedConfigMatchesHardcoded() throws Exception {
    // This test validates that YAML parsing produces identical results
    String yamlContent =
        "name: SMA_EMA_CROSSOVER\n"
            + "description: SMA crosses EMA\n"
            + "complexity: SIMPLE\n"
            + "\n"
            + "indicators:\n"
            + "  - id: sma\n"
            + "    type: SMA\n"
            + "    input: close\n"
            + "    params:\n"
            + "      period: \"${smaPeriod}\"\n"
            + "  - id: ema\n"
            + "    type: EMA\n"
            + "    input: close\n"
            + "    params:\n"
            + "      period: \"${emaPeriod}\"\n"
            + "\n"
            + "entryConditions:\n"
            + "  - type: CROSSED_UP\n"
            + "    indicator: sma\n"
            + "    params:\n"
            + "      crosses: ema\n"
            + "\n"
            + "exitConditions:\n"
            + "  - type: CROSSED_DOWN\n"
            + "    indicator: sma\n"
            + "    params:\n"
            + "      crosses: ema\n"
            + "\n"
            + "parameters:\n"
            + "  - name: smaPeriod\n"
            + "    type: INTEGER\n"
            + "    min: 5\n"
            + "    max: 50\n"
            + "    defaultValue: 20\n"
            + "  - name: emaPeriod\n"
            + "    type: INTEGER\n"
            + "    min: 5\n"
            + "    max: 50\n"
            + "    defaultValue: 50\n";

    StrategyConfig config = StrategyConfigLoader.parseYaml(yamlContent);
    assertNotNull("YAML config should parse successfully", config);

    // Create both strategies with same parameters
    int smaPeriod = 20;
    int emaPeriod = 50;

    SmaEmaCrossoverStrategyFactory hardcodedFactory = new SmaEmaCrossoverStrategyFactory();
    SmaEmaCrossoverParameters hardcodedParams =
        SmaEmaCrossoverParameters.newBuilder()
            .setSmaPeriod(smaPeriod)
            .setEmaPeriod(emaPeriod)
            .build();
    Strategy hardcodedStrategy = hardcodedFactory.createStrategy(testSeries, hardcodedParams);

    ConfigurableStrategyFactory configFactory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters configParams =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("smaPeriod", smaPeriod)
            .putIntValues("emaPeriod", emaPeriod)
            .build();
    Strategy configStrategy = configFactory.createStrategy(testSeries, configParams);

    // Verify signals match
    int warmupPeriod = Math.max(smaPeriod, emaPeriod) + 10;
    for (int i = warmupPeriod; i < testSeries.getBarCount(); i++) {
      assertEquals(
          String.format("Entry signal mismatch at bar %d", i),
          hardcodedStrategy.shouldEnter(i),
          configStrategy.shouldEnter(i));
      assertEquals(
          String.format("Exit signal mismatch at bar %d", i),
          hardcodedStrategy.shouldExit(i),
          configStrategy.shouldExit(i));
    }
  }

  @Test
  public void testConfigWithDifferentParametersProducesDifferentSignals() throws Exception {
    // This test ensures our config system actually uses parameters correctly
    StrategyConfig config =
        StrategyConfig.builder()
            .name("SMA_EMA_CONFIG")
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
                        .max(100)
                        .defaultValue(10)
                        .build(),
                    ParameterDefinition.builder()
                        .name("emaPeriod")
                        .type(ParameterType.INTEGER)
                        .min(5)
                        .max(100)
                        .defaultValue(30)
                        .build()))
            .build();

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);

    // Create two strategies with different parameters
    ConfigurableStrategyParameters params1 =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("smaPeriod", 10)
            .putIntValues("emaPeriod", 30)
            .build();
    Strategy strategy1 = factory.createStrategy(testSeries, params1);

    ConfigurableStrategyParameters params2 =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("smaPeriod", 5)
            .putIntValues("emaPeriod", 50)
            .build();
    Strategy strategy2 = factory.createStrategy(testSeries, params2);

    // Count differences in signals
    int differences = 0;
    for (int i = 60; i < testSeries.getBarCount(); i++) {
      if (strategy1.shouldEnter(i) != strategy2.shouldEnter(i)) {
        differences++;
      }
      if (strategy1.shouldExit(i) != strategy2.shouldExit(i)) {
        differences++;
      }
    }

    // Different parameters should produce different signals (at least some of the time)
    assertTrue(
        "Different parameters should produce at least some different signals", differences > 0);
  }
}
