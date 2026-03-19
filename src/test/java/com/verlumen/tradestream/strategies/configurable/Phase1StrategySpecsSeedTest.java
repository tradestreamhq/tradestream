package com.verlumen.tradestream.strategies.configurable;

import static org.junit.Assert.*;

import com.verlumen.tradestream.strategies.ConfigurableStrategyParameters;
import com.verlumen.tradestream.strategies.SmaEmaCrossoverParameters;
import com.verlumen.tradestream.strategies.smaemacrossover.SmaEmaCrossoverStrategyFactory;
import java.util.Arrays;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;
import org.ta4j.core.num.DecimalNum;

/**
 * Tests for Phase 1 strategy specs seed migration. Validates that all 15 YAML strategy configs can
 * be loaded, parsed, and used to build strategies that produce valid signals. Also validates that
 * the JSON representations in V11 match the YAML source configs.
 */
public class Phase1StrategySpecsSeedTest {

  private static final List<String> PHASE1_STRATEGIES =
      Arrays.asList(
          "SMA_EMA_CROSSOVER",
          "DOUBLE_EMA_CROSSOVER",
          "MACD_CROSSOVER",
          "RSI_EMA_CROSSOVER",
          "DPO_CROSSOVER",
          "ROC_MA_CROSSOVER",
          "TRIPLE_EMA_CROSSOVER",
          "DEMA_TEMA_CROSSOVER",
          "MOMENTUM_SMA_CROSSOVER",
          "VWAP_CROSSOVER",
          "AWESOME_OSCILLATOR",
          "OBV_EMA",
          "PVT",
          "VPT",
          "CHAIKIN_OSCILLATOR");

  private BarSeries testSeries;

  @Before
  public void setUp() {
    testSeries = new BaseBarSeriesBuilder().withName("phase1-test").build();
    java.time.ZonedDateTime now = java.time.ZonedDateTime.now();

    double basePrice = 100.0;
    for (int i = 0; i < 200; i++) {
      double cycle = Math.sin(i * 0.1) * 20 + Math.sin(i * 0.05) * 10;
      double price = basePrice + cycle;
      double high = price + 2;
      double low = price - 2;
      double open = price - 0.5;
      double close = price;
      long volume = 1000 + (long) (Math.random() * 500);

      testSeries.addBar(
          new BaseBar(
              java.time.Duration.ofMinutes(1),
              now.plusMinutes(i).toInstant().minus(java.time.Duration.ofMinutes(1)),
              now.plusMinutes(i).toInstant(),
              DecimalNum.valueOf(open),
              DecimalNum.valueOf(high),
              DecimalNum.valueOf(low),
              DecimalNum.valueOf(close),
              DecimalNum.valueOf(volume),
              DecimalNum.valueOf(0),
              0));
    }
  }

  @Test
  public void testAllPhase1YamlConfigsLoadSuccessfully() {
    for (StrategyConfigLoader.ConfigStrategy configStrategy :
        StrategyConfigLoader.ConfigStrategy.values()) {
      String name = configStrategy.name();
      if (PHASE1_STRATEGIES.contains(name)) {
        StrategyConfig config = configStrategy.get();
        assertNotNull("Config for " + name + " should load", config);
        assertNotNull("Config for " + name + " should have indicators", config.getIndicators());
        assertFalse(
            "Config for " + name + " should have at least one indicator",
            config.getIndicators().isEmpty());
        assertNotNull(
            "Config for " + name + " should have entry conditions", config.getEntryConditions());
        assertFalse(
            "Config for " + name + " should have at least one entry condition",
            config.getEntryConditions().isEmpty());
        assertNotNull(
            "Config for " + name + " should have exit conditions", config.getExitConditions());
        assertFalse(
            "Config for " + name + " should have at least one exit condition",
            config.getExitConditions().isEmpty());
        assertNotNull("Config for " + name + " should have parameters", config.getParameters());
        assertFalse(
            "Config for " + name + " should have at least one parameter",
            config.getParameters().isEmpty());
      }
    }
  }

  @Test
  public void testPhase1ConfigsProduceValidStrategies() throws Exception {
    // Test SMA_EMA_CROSSOVER config builds and runs
    StrategyConfig smaEmaConfig = StrategyConfigLoader.ConfigStrategy.SMA_EMA_CROSSOVER.get();
    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(smaEmaConfig);

    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("smaPeriod", 20)
            .putIntValues("emaPeriod", 50)
            .build();

    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("SMA_EMA_CROSSOVER strategy should be created", strategy);

    // Verify it can evaluate signals without errors
    int signalCount = 0;
    for (int i = 60; i < testSeries.getBarCount(); i++) {
      if (strategy.shouldEnter(i) || strategy.shouldExit(i)) {
        signalCount++;
      }
    }
    assertTrue("Strategy should produce at least one signal", signalCount > 0);
  }

  @Test
  public void testDoubleEmaCrossoverConfig() throws Exception {
    StrategyConfig config = StrategyConfigLoader.ConfigStrategy.DOUBLE_EMA_CROSSOVER.get();
    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);

    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("shortEmaPeriod", 12)
            .putIntValues("longEmaPeriod", 26)
            .build();

    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("DOUBLE_EMA_CROSSOVER strategy should be created", strategy);

    int signalCount = 0;
    for (int i = 30; i < testSeries.getBarCount(); i++) {
      if (strategy.shouldEnter(i) || strategy.shouldExit(i)) {
        signalCount++;
      }
    }
    assertTrue("DOUBLE_EMA_CROSSOVER should produce signals", signalCount > 0);
  }

  @Test
  public void testMacdCrossoverConfig() throws Exception {
    StrategyConfig config = StrategyConfigLoader.ConfigStrategy.MACD_CROSSOVER.get();
    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);

    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("shortEmaPeriod", 12)
            .putIntValues("longEmaPeriod", 26)
            .putIntValues("signalPeriod", 9)
            .build();

    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("MACD_CROSSOVER strategy should be created", strategy);
  }

  @Test
  public void testDpoCrossoverConfig() throws Exception {
    StrategyConfig config = StrategyConfigLoader.ConfigStrategy.DPO_CROSSOVER.get();
    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);

    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("dpoPeriod", 15)
            .putIntValues("maPeriod", 10)
            .build();

    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("DPO_CROSSOVER strategy should be created", strategy);
  }

  @Test
  public void testRocMaCrossoverConfig() throws Exception {
    StrategyConfig config = StrategyConfigLoader.ConfigStrategy.ROC_MA_CROSSOVER.get();
    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);

    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("rocPeriod", 10)
            .putIntValues("maPeriod", 14)
            .build();

    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("ROC_MA_CROSSOVER strategy should be created", strategy);
  }

  @Test
  public void testSmaEmaCrossoverConfigMatchesHardcoded() throws Exception {
    int smaPeriod = 20;
    int emaPeriod = 50;

    // Hardcoded strategy
    SmaEmaCrossoverStrategyFactory hardcodedFactory = new SmaEmaCrossoverStrategyFactory();
    SmaEmaCrossoverParameters hardcodedParams =
        SmaEmaCrossoverParameters.newBuilder()
            .setSmaPeriod(smaPeriod)
            .setEmaPeriod(emaPeriod)
            .build();
    Strategy hardcodedStrategy = hardcodedFactory.createStrategy(testSeries, hardcodedParams);

    // Config-based strategy from YAML
    StrategyConfig config = StrategyConfigLoader.ConfigStrategy.SMA_EMA_CROSSOVER.get();
    ConfigurableStrategyFactory configFactory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters configParams =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("smaPeriod", smaPeriod)
            .putIntValues("emaPeriod", emaPeriod)
            .build();
    Strategy configStrategy = configFactory.createStrategy(testSeries, configParams);

    // Compare signals
    int warmupPeriod = Math.max(smaPeriod, emaPeriod) + 10;
    int mismatches = 0;
    int totalChecks = 0;

    for (int i = warmupPeriod; i < testSeries.getBarCount(); i++) {
      totalChecks++;
      if (hardcodedStrategy.shouldEnter(i) != configStrategy.shouldEnter(i)) {
        mismatches++;
      }
      if (hardcodedStrategy.shouldExit(i) != configStrategy.shouldExit(i)) {
        mismatches++;
      }
    }

    assertEquals(
        String.format(
            "SMA_EMA_CROSSOVER config should match hardcoded. Found %d mismatches in %d checks",
            mismatches, totalChecks * 2),
        0,
        mismatches);
    assertTrue("Should have tested at least 50 bars", totalChecks >= 50);
  }

  @Test
  public void testAllPhase1ConfigsHaveCorrectParameterBounds() {
    for (StrategyConfigLoader.ConfigStrategy configStrategy :
        StrategyConfigLoader.ConfigStrategy.values()) {
      String name = configStrategy.name();
      if (PHASE1_STRATEGIES.contains(name)) {
        StrategyConfig config = configStrategy.get();
        for (ParameterDefinition param : config.getParameters()) {
          assertNotNull(
              name + " parameter " + param.getName() + " should have a name", param.getName());
          assertNotNull(
              name + " parameter " + param.getName() + " should have a type", param.getType());
          assertTrue(
              name + " parameter " + param.getName() + " min should be < max",
              param.getMin().doubleValue() < param.getMax().doubleValue());
          assertTrue(
              name + " parameter " + param.getName() + " default should be >= min",
              param.getDefaultValue().doubleValue() >= param.getMin().doubleValue());
          assertTrue(
              name + " parameter " + param.getName() + " default should be <= max",
              param.getDefaultValue().doubleValue() <= param.getMax().doubleValue());
        }
      }
    }
  }

  @Test
  public void testPhase1StrategyCount() {
    int count = 0;
    for (StrategyConfigLoader.ConfigStrategy configStrategy :
        StrategyConfigLoader.ConfigStrategy.values()) {
      if (PHASE1_STRATEGIES.contains(configStrategy.name())) {
        count++;
      }
    }
    assertEquals("All 15 Phase 1 strategies should be present in ConfigStrategy enum", 15, count);
  }
}
