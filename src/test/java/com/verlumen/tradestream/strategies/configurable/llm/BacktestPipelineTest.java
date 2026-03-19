package com.verlumen.tradestream.strategies.configurable.llm;

import static org.junit.Assert.*;

import com.verlumen.tradestream.strategies.configurable.ConditionConfig;
import com.verlumen.tradestream.strategies.configurable.IndicatorConfig;
import com.verlumen.tradestream.strategies.configurable.ParameterDefinition;
import com.verlumen.tradestream.strategies.configurable.ParameterType;
import com.verlumen.tradestream.strategies.configurable.StrategyConfig;
import java.util.List;
import java.util.Map;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;

public class BacktestPipelineTest {

  private BacktestPipeline pipeline;
  private BarSeries barSeries;

  @Before
  public void setUp() {
    pipeline = new BacktestPipeline();
    barSeries = BacktestPipeline.generateSyntheticBars(200, 42L);
  }

  @Test
  public void generateSyntheticBars_createsCorrectCount() {
    BarSeries series = BacktestPipeline.generateSyntheticBars(100, 1L);
    assertEquals(100, series.getBarCount());
  }

  @Test
  public void generateSyntheticBars_deterministic() {
    BarSeries a = BacktestPipeline.generateSyntheticBars(50, 42L);
    BarSeries b = BacktestPipeline.generateSyntheticBars(50, 42L);

    assertEquals(a.getBarCount(), b.getBarCount());
    for (int i = 0; i < a.getBarCount(); i++) {
      assertEquals(
          a.getBar(i).getClosePrice().doubleValue(),
          b.getBar(i).getClosePrice().doubleValue(),
          0.0001);
    }
  }

  @Test
  public void generateSyntheticBars_validPrices() {
    BarSeries series = BacktestPipeline.generateSyntheticBars(100, 42L);
    for (int i = 0; i < series.getBarCount(); i++) {
      double high = series.getBar(i).getHighPrice().doubleValue();
      double low = series.getBar(i).getLowPrice().doubleValue();
      double open = series.getBar(i).getOpenPrice().doubleValue();
      double close = series.getBar(i).getClosePrice().doubleValue();

      assertTrue("High should be >= Open", high >= open - 0.001);
      assertTrue("High should be >= Close", high >= close - 0.001);
      assertTrue("Low should be <= Open", low <= open + 0.001);
      assertTrue("Low should be <= Close", low <= close + 0.001);
      assertTrue("Prices should be positive", close > 0);
    }
  }

  @Test
  public void runBacktest_validConfig_returnsResult() {
    StrategyConfig config = createValidConfig("BACKTEST_TEST");
    BacktestPipeline.BacktestResult result = pipeline.runBacktest(config, barSeries);

    assertNotNull(result);
    assertTrue("Should be successful", result.isSuccessful());
    assertEquals("BACKTEST_TEST", result.getStrategyName());
    assertNull(result.getError());
    // Gross return should be a number (could be < 1 for losses)
    assertFalse(Double.isNaN(result.getGrossReturn()));
  }

  @Test
  public void runBacktest_validConfig_producesMetrics() {
    StrategyConfig config = createValidConfig("METRICS_TEST");
    BacktestPipeline.BacktestResult result = pipeline.runBacktest(config, barSeries);

    assertTrue(result.isSuccessful());
    // Win rate should be between 0 and 1
    assertTrue(result.getWinRate() >= 0.0 && result.getWinRate() <= 1.0);
    // Number of trades should be non-negative
    assertTrue(result.getNumTrades() >= 0);
  }

  @Test
  public void runBacktest_invalidConfig_returnsError() {
    // Config with no indicators - should fail to build
    StrategyConfig config =
        StrategyConfig.builder()
            .name("BAD_CONFIG")
            .description("Broken config")
            .complexity("SIMPLE")
            .indicators(List.of())
            .entryConditions(
                List.of(
                    ConditionConfig.builder()
                        .type("CROSSED_UP")
                        .indicator("nonexistent")
                        .params(Map.of("crosses", "also_nonexistent"))
                        .build()))
            .exitConditions(
                List.of(
                    ConditionConfig.builder()
                        .type("CROSSED_DOWN")
                        .indicator("nonexistent")
                        .params(Map.of("crosses", "also_nonexistent"))
                        .build()))
            .parameters(List.of())
            .build();

    BacktestPipeline.BacktestResult result = pipeline.runBacktest(config, barSeries);
    assertNotNull(result);
    assertFalse(result.isSuccessful());
    assertNotNull(result.getError());
  }

  @Test
  public void runBacktest_toString_formatsCorrectly() {
    StrategyConfig config = createValidConfig("FORMAT_TEST");
    BacktestPipeline.BacktestResult result = pipeline.runBacktest(config, barSeries);
    String str = result.toString();
    assertNotNull(str);
    assertTrue(str.contains("FORMAT_TEST"));
  }

  private StrategyConfig createValidConfig(String name) {
    return StrategyConfig.builder()
        .name(name)
        .description("Test strategy for backtesting")
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
                    .defaultValue(10)
                    .build(),
                ParameterDefinition.builder()
                    .name("emaPeriod")
                    .type(ParameterType.INTEGER)
                    .min(5)
                    .max(50)
                    .defaultValue(20)
                    .build()))
        .build();
  }
}
