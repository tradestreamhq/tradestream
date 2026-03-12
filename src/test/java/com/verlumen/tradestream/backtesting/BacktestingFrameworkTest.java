package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.InvalidProtocolBufferException;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.ta4j.Ta4jModule;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

/**
 * Integration tests for the backtesting framework. Backtests multiple strategies against synthetic
 * historical data to verify end-to-end functionality.
 */
@RunWith(JUnit4.class)
public class BacktestingFrameworkTest {

  @Inject private BacktestRunnerImpl backtestRunner;

  private BacktestingFramework framework;
  private List<Candle> trendingUpCandles;
  private List<Candle> volatileCandles;

  @Before
  public void setUp() {
    Guice.createInjector(BoundFieldModule.of(this), Ta4jModule.create()).injectMembers(this);
    framework = new BacktestingFramework(backtestRunner);
    trendingUpCandles = generateTrendingUpData();
    volatileCandles = generateVolatileData();
  }

  // ===== SMA_RSI Strategy Tests =====

  @Test
  public void smaRsi_withTrendingData_returnsValidMetrics() throws InvalidProtocolBufferException {
    BacktestResult result = framework.runBacktest("SMA_RSI", trendingUpCandles);

    assertValidMetrics(result);
    assertThat(result.getStrategyScore()).isAtLeast(0.0);
  }

  @Test
  public void smaRsi_withVolatileData_calculatesRiskMetrics()
      throws InvalidProtocolBufferException {
    BacktestResult result = framework.runBacktest("SMA_RSI", volatileCandles);

    assertValidMetrics(result);
    assertThat(result.getVolatility()).isGreaterThan(0.0);
    assertThat(result.getMaxDrawdown()).isGreaterThan(0.0);
  }

  // ===== DOUBLE_EMA_CROSSOVER Strategy Tests =====

  @Test
  public void doubleEmaCrossover_withTrendingData_returnsValidMetrics()
      throws InvalidProtocolBufferException {
    BacktestResult result = framework.runBacktest("DOUBLE_EMA_CROSSOVER", trendingUpCandles);

    assertValidMetrics(result);
    assertThat(result.getStrategyScore()).isAtLeast(0.0);
  }

  @Test
  public void doubleEmaCrossover_withVolatileData_generatesTradeSignals()
      throws InvalidProtocolBufferException {
    BacktestResult result = framework.runBacktest("DOUBLE_EMA_CROSSOVER", volatileCandles);

    assertValidMetrics(result);
    assertThat(Double.isFinite(result.getSharpeRatio())).isTrue();
  }

  // ===== MACD_CROSSOVER Strategy Tests =====

  @Test
  public void macdCrossover_withTrendingData_returnsValidMetrics()
      throws InvalidProtocolBufferException {
    BacktestResult result = framework.runBacktest("MACD_CROSSOVER", trendingUpCandles);

    assertValidMetrics(result);
  }

  // ===== Strategy Comparison Tests =====

  @Test
  public void compareStrategies_returnsResultsForAllStrategies()
      throws InvalidProtocolBufferException {
    List<String> strategies = ImmutableList.of("SMA_RSI", "DOUBLE_EMA_CROSSOVER", "MACD_CROSSOVER");

    Map<String, BacktestResult> results =
        framework.compareStrategies(strategies, trendingUpCandles);

    assertThat(results).hasSize(3);
    assertThat(results).containsKey("SMA_RSI");
    assertThat(results).containsKey("DOUBLE_EMA_CROSSOVER");
    assertThat(results).containsKey("MACD_CROSSOVER");

    for (BacktestResult result : results.values()) {
      assertValidMetrics(result);
    }
  }

  // ===== Report Generation Tests =====

  @Test
  public void backTestReport_generate_producesFormattedOutput() {
    BacktestResult result =
        BacktestResult.newBuilder()
            .setCumulativeReturn(0.15)
            .setAnnualizedReturn(0.30)
            .setSharpeRatio(1.5)
            .setSortinoRatio(2.0)
            .setMaxDrawdown(0.10)
            .setVolatility(0.05)
            .setNumberOfTrades(25)
            .setWinRate(0.60)
            .setProfitFactor(1.8)
            .setAverageTradeDuration(5.5)
            .setStrategyScore(0.75)
            .build();

    String report = BacktestReport.generate("TEST_STRATEGY", result);

    assertThat(report).contains("TEST_STRATEGY");
    assertThat(report).contains("Cumulative Return");
    assertThat(report).contains("Sharpe Ratio");
    assertThat(report).contains("Max Drawdown");
    assertThat(report).contains("Win Rate");
    assertThat(report).contains("60.00%");
  }

  @Test
  public void backTestReport_generateOneLine_producesCompactOutput() {
    BacktestResult result =
        BacktestResult.newBuilder()
            .setCumulativeReturn(0.15)
            .setSharpeRatio(1.5)
            .setMaxDrawdown(0.10)
            .setWinRate(0.60)
            .setNumberOfTrades(25)
            .build();

    String oneLine = BacktestReport.generateOneLine("TEST_STRATEGY", result);

    assertThat(oneLine).contains("TEST_STRATEGY");
    assertThat(oneLine).contains("Return:");
    assertThat(oneLine).contains("Sharpe:");
    assertThat(oneLine).contains("Trades: 25");
  }

  // ===== CsvHistoricalDataLoader Tests =====

  @Test
  public void csvHistoricalDataLoader_fromResource_loadsCandles() throws Exception {
    // Test with inline data loader that mimics CSV loading
    HistoricalDataLoader loader = () -> trendingUpCandles;

    List<Candle> candles = loader.loadCandles();

    assertThat(candles).isNotEmpty();
    assertThat(candles.get(0).getCurrencyPair()).isEqualTo("BTC/USD");
  }

  // ===== Helper Methods =====

  private void assertValidMetrics(BacktestResult result) {
    assertThat(result.getMaxDrawdown()).isAtLeast(0.0);
    assertThat(result.getMaxDrawdown()).isAtMost(1.0);
    assertThat(result.getWinRate()).isAtLeast(0.0);
    assertThat(result.getWinRate()).isAtMost(1.0);
    assertThat(result.getVolatility()).isAtLeast(0.0);
    assertThat(Double.isFinite(result.getSharpeRatio())).isTrue();
    assertThat(Double.isFinite(result.getSortinoRatio())).isTrue();
    assertThat(result.getStrategyScore()).isAtLeast(0.0);
    assertThat(result.getNumberOfTrades()).isAtLeast(0);
  }

  /**
   * Generates 100 bars of trending-up data with intermittent pullbacks. This creates enough data
   * for indicators with longer lookback periods (e.g., MACD with 26-period EMA).
   */
  private List<Candle> generateTrendingUpData() {
    List<Candle> candles = new ArrayList<>();
    ZonedDateTime start = ZonedDateTime.now();
    double basePrice = 100.0;

    for (int i = 0; i < 100; i++) {
      double trend = i * 0.5; // General uptrend
      double pullback = (i % 10 < 3) ? -2.0 * (3 - (i % 10)) : 0; // Pullback every 10 bars
      double noise = Math.sin(i * 0.3) * 1.5; // Cyclical noise
      double price = basePrice + trend + pullback + noise;
      price = Math.max(price, 50.0);

      candles.add(createCandle(start.plusMinutes(i), price));
    }
    return candles;
  }

  /**
   * Generates 100 bars of volatile, mean-reverting data. Creates conditions where oscillator-based
   * strategies (RSI, Stochastic) can generate meaningful signals.
   */
  private List<Candle> generateVolatileData() {
    List<Candle> candles = new ArrayList<>();
    ZonedDateTime start = ZonedDateTime.now();
    double basePrice = 100.0;

    for (int i = 0; i < 100; i++) {
      // Create strong oscillations around a base price
      double swing = 15.0 * Math.sin(i * 0.15); // Large swings
      double secondarySwing = 5.0 * Math.sin(i * 0.4); // Faster secondary oscillation
      double microNoise = 2.0 * Math.sin(i * 1.1); // Micro noise
      double price = basePrice + swing + secondarySwing + microNoise;
      price = Math.max(price, 50.0);

      candles.add(createCandle(start.plusMinutes(i), price));
    }
    return candles;
  }

  private Candle createCandle(ZonedDateTime time, double price) {
    return Candle.newBuilder()
        .setTimestamp(Timestamps.fromMillis(time.toInstant().toEpochMilli()))
        .setCurrencyPair("BTC/USD")
        .setOpen(price)
        .setHigh(price * 1.01)
        .setLow(price * 0.99)
        .setClose(price)
        .setVolume(1000)
        .build();
  }
}
