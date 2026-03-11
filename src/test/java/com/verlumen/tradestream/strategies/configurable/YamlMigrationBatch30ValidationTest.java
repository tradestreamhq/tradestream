package com.verlumen.tradestream.strategies.configurable;

import static org.junit.Assert.*;

import com.verlumen.tradestream.strategies.ConfigurableStrategyParameters;
import com.verlumen.tradestream.strategies.configurable.StrategyConfigLoader.ConfigStrategy;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;

/**
 * Validation tests for YAML migration batch 30: CMF_ZERO_LINE, DEMA_TEMA_CROSSOVER,
 * DOUBLE_EMA_CROSSOVER, ELDER_RAY_MA, MOMENTUM_SMA_CROSSOVER. Verifies YAML configs load correctly
 * and produce valid strategies.
 */
public class YamlMigrationBatch30ValidationTest {

  private BarSeries testSeries;

  @Before
  public void setUp() {
    testSeries = new BaseBarSeriesBuilder().withName("batch30-validation").build();

    double basePrice = 100.0;
    for (int i = 0; i < 200; i++) {
      double cycle = Math.sin(i * 0.1) * 20 + Math.sin(i * 0.05) * 10;
      double price = basePrice + cycle;
      double high = price + 2;
      double low = price - 2;
      double open = price - 0.5;
      double close = price;
      long volume = 1000 + (long) (Math.abs(Math.sin(i * 0.3)) * 500);

      testSeries.addBar(
          java.time.ZonedDateTime.now().plusMinutes(i), open, high, low, close, volume);
    }
  }

  @Test
  public void testCmfZeroLineConfigLoads() {
    StrategyConfig config = ConfigStrategy.CMF_ZERO_LINE.get();
    assertNotNull("CMF_ZERO_LINE config should load", config);
    assertEquals("CMF_ZERO_LINE", config.getName());
    assertFalse("Should have indicators", config.getIndicators().isEmpty());
    assertFalse("Should have entry conditions", config.getEntryConditions().isEmpty());
    assertFalse("Should have exit conditions", config.getExitConditions().isEmpty());
  }

  @Test
  public void testCmfZeroLineCreatesStrategy() {
    StrategyConfig config = ConfigStrategy.CMF_ZERO_LINE.get();
    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder().putIntValues("period", 20).build();
    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("Should create strategy", strategy);
  }

  @Test
  public void testDemaTemaCrossoverConfigLoads() {
    StrategyConfig config = ConfigStrategy.DEMA_TEMA_CROSSOVER.get();
    assertNotNull("DEMA_TEMA_CROSSOVER config should load", config);
    assertEquals("DEMA_TEMA_CROSSOVER", config.getName());
    assertFalse("Should have indicators", config.getIndicators().isEmpty());
    assertFalse("Should have entry conditions", config.getEntryConditions().isEmpty());
    assertFalse("Should have exit conditions", config.getExitConditions().isEmpty());
  }

  @Test
  public void testDemaTemaCrossoverCreatesStrategy() {
    StrategyConfig config = ConfigStrategy.DEMA_TEMA_CROSSOVER.get();
    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("demaPeriod", 12)
            .putIntValues("temaPeriod", 26)
            .build();
    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("Should create strategy", strategy);
  }

  @Test
  public void testDoubleEmaCrossoverConfigLoads() {
    StrategyConfig config = ConfigStrategy.DOUBLE_EMA_CROSSOVER.get();
    assertNotNull("DOUBLE_EMA_CROSSOVER config should load", config);
    assertEquals("DOUBLE_EMA_CROSSOVER", config.getName());
    assertFalse("Should have indicators", config.getIndicators().isEmpty());
    assertFalse("Should have entry conditions", config.getEntryConditions().isEmpty());
    assertFalse("Should have exit conditions", config.getExitConditions().isEmpty());
  }

  @Test
  public void testDoubleEmaCrossoverCreatesStrategy() {
    StrategyConfig config = ConfigStrategy.DOUBLE_EMA_CROSSOVER.get();
    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("shortEmaPeriod", 10)
            .putIntValues("longEmaPeriod", 30)
            .build();
    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("Should create strategy", strategy);
  }

  @Test
  public void testElderRayMaConfigLoads() {
    StrategyConfig config = ConfigStrategy.ELDER_RAY_MA.get();
    assertNotNull("ELDER_RAY_MA config should load", config);
    assertEquals("ELDER_RAY_MA", config.getName());
    assertFalse("Should have indicators", config.getIndicators().isEmpty());
    assertFalse("Should have entry conditions", config.getEntryConditions().isEmpty());
    assertFalse("Should have exit conditions", config.getExitConditions().isEmpty());
  }

  @Test
  public void testElderRayMaCreatesStrategy() {
    StrategyConfig config = ConfigStrategy.ELDER_RAY_MA.get();
    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder().putIntValues("emaPeriod", 20).build();
    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("Should create strategy", strategy);
  }

  @Test
  public void testMomentumSmaCrossoverConfigLoads() {
    StrategyConfig config = ConfigStrategy.MOMENTUM_SMA_CROSSOVER.get();
    assertNotNull("MOMENTUM_SMA_CROSSOVER config should load", config);
    assertEquals("MOMENTUM_SMA_CROSSOVER", config.getName());
    assertFalse("Should have indicators", config.getIndicators().isEmpty());
    assertFalse("Should have entry conditions", config.getEntryConditions().isEmpty());
    assertFalse("Should have exit conditions", config.getExitConditions().isEmpty());
  }

  @Test
  public void testMomentumSmaCrossoverCreatesStrategy() {
    StrategyConfig config = ConfigStrategy.MOMENTUM_SMA_CROSSOVER.get();
    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("momentumPeriod", 10)
            .putIntValues("smaPeriod", 14)
            .build();
    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("Should create strategy", strategy);
  }

  @Test
  public void testAllFiveStrategiesProduceSignals() {
    // Verify that each strategy produces at least some entry or exit signals
    Object[][] strategyConfigs = {
      {ConfigStrategy.CMF_ZERO_LINE, new String[] {"period"}, new int[] {20}},
      {
        ConfigStrategy.DEMA_TEMA_CROSSOVER,
        new String[] {"demaPeriod", "temaPeriod"},
        new int[] {12, 26}
      },
      {
        ConfigStrategy.DOUBLE_EMA_CROSSOVER,
        new String[] {"shortEmaPeriod", "longEmaPeriod"},
        new int[] {10, 30}
      },
      {ConfigStrategy.ELDER_RAY_MA, new String[] {"emaPeriod"}, new int[] {20}},
      {
        ConfigStrategy.MOMENTUM_SMA_CROSSOVER,
        new String[] {"momentumPeriod", "smaPeriod"},
        new int[] {10, 14}
      },
    };

    for (Object[] entry : strategyConfigs) {
      ConfigStrategy cs = (ConfigStrategy) entry[0];
      String[] paramNames = (String[]) entry[1];
      int[] paramValues = (int[]) entry[2];

      StrategyConfig config = cs.get();
      ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);

      ConfigurableStrategyParameters.Builder paramsBuilder =
          ConfigurableStrategyParameters.newBuilder();
      for (int i = 0; i < paramNames.length; i++) {
        paramsBuilder.putIntValues(paramNames[i], paramValues[i]);
      }
      Strategy strategy = factory.createStrategy(testSeries, paramsBuilder.build());

      int signals = 0;
      for (int i = 50; i < testSeries.getBarCount(); i++) {
        if (strategy.shouldEnter(i) || strategy.shouldExit(i)) {
          signals++;
        }
      }

      assertTrue(
          String.format("%s should produce at least one signal over 150 bars", config.getName()),
          signals > 0);
    }
  }
}
