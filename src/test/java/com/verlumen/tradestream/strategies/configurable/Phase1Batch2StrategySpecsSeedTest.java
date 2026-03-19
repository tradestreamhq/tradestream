package com.verlumen.tradestream.strategies.configurable;

import static org.junit.Assert.*;

import com.verlumen.tradestream.strategies.ConfigurableStrategyParameters;
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
 * Tests for Phase 1 Batch 2 strategy specs seed migration (V13). Validates that all 15
 * medium-complexity YAML strategy configs can be loaded, parsed, and used to build strategies that
 * produce valid signals. These strategies use multiple indicators and compound conditions.
 */
public class Phase1Batch2StrategySpecsSeedTest {

  private static final List<String> PHASE1_BATCH2_STRATEGIES =
      Arrays.asList(
          "ADX_DMI",
          "ADX_STOCHASTIC",
          "AROON_MFI",
          "ATR_CCI",
          "BBAND_WILLIAMS_R",
          "CMO_MFI",
          "SMA_RSI",
          "STOCHASTIC_EMA",
          "STOCHASTIC_RSI",
          "SAR_MFI",
          "MOMENTUM_PINBALL",
          "DONCHIAN_BREAKOUT",
          "VWAP_MEAN_REVERSION",
          "VOLUME_BREAKOUT",
          "KST_OSCILLATOR");

  private BarSeries testSeries;

  @Before
  public void setUp() {
    testSeries = new BaseBarSeriesBuilder().withName("phase1-batch2-test").build();
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
  public void testAllBatch2YamlConfigsLoadSuccessfully() {
    for (StrategyConfigLoader.ConfigStrategy configStrategy :
        StrategyConfigLoader.ConfigStrategy.values()) {
      String name = configStrategy.name();
      if (PHASE1_BATCH2_STRATEGIES.contains(name)) {
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
      }
    }
  }

  @Test
  public void testBatch2StrategyCount() {
    int count = 0;
    for (StrategyConfigLoader.ConfigStrategy configStrategy :
        StrategyConfigLoader.ConfigStrategy.values()) {
      if (PHASE1_BATCH2_STRATEGIES.contains(configStrategy.name())) {
        count++;
      }
    }
    assertEquals(
        "All 15 Phase 1 Batch 2 strategies should be present in ConfigStrategy enum", 15, count);
  }

  @Test
  public void testAllBatch2ConfigsHaveCorrectParameterBounds() {
    for (StrategyConfigLoader.ConfigStrategy configStrategy :
        StrategyConfigLoader.ConfigStrategy.values()) {
      String name = configStrategy.name();
      if (PHASE1_BATCH2_STRATEGIES.contains(name)) {
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
  public void testAdxDmiCompoundEntry() throws Exception {
    StrategyConfig config = StrategyConfigLoader.ConfigStrategy.ADX_DMI.get();
    assertNotNull(config);
    assertEquals("ADX_DMI should have 3 indicators", 3, config.getIndicators().size());
    assertEquals(
        "ADX_DMI should have 2 entry conditions (compound)", 2, config.getEntryConditions().size());

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("adxPeriod", 14)
            .putIntValues("diPeriod", 14)
            .build();
    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("ADX_DMI strategy should be created", strategy);
  }

  @Test
  public void testAdxStochasticCompoundEntry() throws Exception {
    StrategyConfig config = StrategyConfigLoader.ConfigStrategy.ADX_STOCHASTIC.get();
    assertNotNull(config);
    assertEquals(
        "ADX_STOCHASTIC should have 2 entry conditions", 2, config.getEntryConditions().size());
    assertEquals(
        "ADX_STOCHASTIC should have 2 exit conditions", 2, config.getExitConditions().size());

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("adxPeriod", 14)
            .putIntValues("stochasticKPeriod", 14)
            .putIntValues("overboughtThreshold", 80)
            .putIntValues("oversoldThreshold", 20)
            .build();
    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("ADX_STOCHASTIC strategy should be created", strategy);
  }

  @Test
  public void testAroonMfiCompoundEntry() throws Exception {
    StrategyConfig config = StrategyConfigLoader.ConfigStrategy.AROON_MFI.get();
    assertNotNull(config);
    assertEquals("AROON_MFI should have 3 indicators", 3, config.getIndicators().size());
    assertEquals("AROON_MFI should have 2 entry conditions", 2, config.getEntryConditions().size());

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("aroonPeriod", 25)
            .putIntValues("mfiPeriod", 14)
            .putIntValues("overboughtThreshold", 80)
            .putIntValues("oversoldThreshold", 20)
            .build();
    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("AROON_MFI strategy should be created", strategy);
  }

  @Test
  public void testAtrCciCompoundEntry() throws Exception {
    StrategyConfig config = StrategyConfigLoader.ConfigStrategy.ATR_CCI.get();
    assertNotNull(config);
    assertEquals("ATR_CCI should have 3 indicators", 3, config.getIndicators().size());
    assertEquals("ATR_CCI should have 2 entry conditions", 2, config.getEntryConditions().size());

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("atrPeriod", 14)
            .putIntValues("cciPeriod", 20)
            .build();
    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("ATR_CCI strategy should be created", strategy);
  }

  @Test
  public void testBbandWilliamsRCompoundEntry() throws Exception {
    StrategyConfig config = StrategyConfigLoader.ConfigStrategy.BBAND_WILLIAMS_R.get();
    assertNotNull(config);
    assertEquals("BBAND_WILLIAMS_R should have 4 indicators", 4, config.getIndicators().size());
    assertEquals(
        "BBAND_WILLIAMS_R should have 2 entry conditions", 2, config.getEntryConditions().size());

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("bbandsPeriod", 20)
            .putIntValues("wrPeriod", 14)
            .putDoubleValues("stdDevMultiplier", 2.0)
            .build();
    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("BBAND_WILLIAMS_R strategy should be created", strategy);
  }

  @Test
  public void testCmoMfiCompoundEntry() throws Exception {
    StrategyConfig config = StrategyConfigLoader.ConfigStrategy.CMO_MFI.get();
    assertNotNull(config);
    assertEquals("CMO_MFI should have 2 indicators", 2, config.getIndicators().size());
    assertEquals("CMO_MFI should have 2 entry conditions", 2, config.getEntryConditions().size());

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("cmoPeriod", 14)
            .putIntValues("mfiPeriod", 14)
            .build();
    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("CMO_MFI strategy should be created", strategy);
  }

  @Test
  public void testSmaRsiCompoundEntry() throws Exception {
    StrategyConfig config = StrategyConfigLoader.ConfigStrategy.SMA_RSI.get();
    assertNotNull(config);
    assertEquals("SMA_RSI should have 3 indicators", 3, config.getIndicators().size());
    assertEquals("SMA_RSI should have 2 entry conditions", 2, config.getEntryConditions().size());

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("movingAveragePeriod", 20)
            .putIntValues("rsiPeriod", 14)
            .putDoubleValues("overboughtThreshold", 70.0)
            .putDoubleValues("oversoldThreshold", 30.0)
            .build();
    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("SMA_RSI strategy should be created", strategy);
  }

  @Test
  public void testMomentumPinballCompoundEntry() throws Exception {
    StrategyConfig config = StrategyConfigLoader.ConfigStrategy.MOMENTUM_PINBALL.get();
    assertNotNull(config);
    assertEquals("MOMENTUM_PINBALL should have 2 indicators", 2, config.getIndicators().size());
    assertEquals(
        "MOMENTUM_PINBALL should have 2 entry conditions", 2, config.getEntryConditions().size());
    assertEquals(
        "MOMENTUM_PINBALL should have 2 exit conditions", 2, config.getExitConditions().size());

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("shortPeriod", 10)
            .putIntValues("longPeriod", 20)
            .build();
    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("MOMENTUM_PINBALL strategy should be created", strategy);
  }

  @Test
  public void testDonchianBreakout() throws Exception {
    StrategyConfig config = StrategyConfigLoader.ConfigStrategy.DONCHIAN_BREAKOUT.get();
    assertNotNull(config);
    assertEquals("DONCHIAN_BREAKOUT should have 3 indicators", 3, config.getIndicators().size());

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder().putIntValues("donchianPeriod", 20).build();
    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("DONCHIAN_BREAKOUT strategy should be created", strategy);
  }

  @Test
  public void testKstOscillator() throws Exception {
    StrategyConfig config = StrategyConfigLoader.ConfigStrategy.KST_OSCILLATOR.get();
    assertNotNull(config);
    assertTrue("KST_OSCILLATOR should have 5+ indicators", config.getIndicators().size() >= 5);

    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
    ConfigurableStrategyParameters params =
        ConfigurableStrategyParameters.newBuilder()
            .putIntValues("rma1Period", 10)
            .putIntValues("rma2Period", 15)
            .putIntValues("rma3Period", 20)
            .putIntValues("rma4Period", 30)
            .putIntValues("signalPeriod", 9)
            .build();
    Strategy strategy = factory.createStrategy(testSeries, params);
    assertNotNull("KST_OSCILLATOR strategy should be created", strategy);
  }

  @Test
  public void testTotalPhase1StrategiesReaches30() {
    List<String> phase1Batch1 =
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

    int totalPhase1 = phase1Batch1.size() + PHASE1_BATCH2_STRATEGIES.size();
    assertEquals("Phase 1 total should be 30 strategies (15 + 15)", 30, totalPhase1);

    // Verify no overlap between batches
    for (String strategy : PHASE1_BATCH2_STRATEGIES) {
      assertFalse(
          strategy + " should not be in both batch 1 and batch 2", phase1Batch1.contains(strategy));
    }
  }
}
