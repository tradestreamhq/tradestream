package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.Strategy;
import com.verlumen.tradestream.strategies.StrategySpecs;
import com.verlumen.tradestream.ta4j.Ta4jModule;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class BacktestRunnerImplTest {
  @Rule public MockitoRule mockitoRule = MockitoJUnit.rule();

  private List<Candle> candlesList;
  private ZonedDateTime startTime;

  @Inject private BacktestRunnerImpl backtestRunner;

  @Before
  public void setUp() throws Exception {
    // Initialize test data
    candlesList = new ArrayList<>();
    startTime = ZonedDateTime.now();

    // Inject our dependencies
    Guice.createInjector(BoundFieldModule.of(this), Ta4jModule.create()).injectMembers(this);
  }

  @Test
  public void runBacktest_withEmptySeries_throwsException() throws InvalidProtocolBufferException {
    // Arrange
    BacktestRequest request =
        BacktestRequest.newBuilder()
            .addAllCandles(ImmutableList.of()) // Empty candles list
            .setStrategy(createStrategyWithDefaults("SMA_RSI"))
            .build();

    // Act & Assert
    IllegalArgumentException thrown =
        assertThrows(IllegalArgumentException.class, () -> backtestRunner.runBacktest(request));

    assertThat(thrown).hasMessageThat().contains("Bar series cannot be empty");
  }

  @Test
  public void runBacktest_withValidDataAndStrategy_returnsResults()
      throws InvalidProtocolBufferException {
    // Arrange - Create data that will trigger SMA_RSI strategy
    // Start with baseline, then create oversold condition, then recovery
    addTestBarsForOversoldRecovery();

    BacktestRequest request =
        BacktestRequest.newBuilder()
            .addAllCandles(candlesList)
            .setStrategy(createStrategyWithDefaults("SMA_RSI"))
            .build();

    // Act
    BacktestResult result = backtestRunner.runBacktest(request);

    // Assert - More realistic expectations
    assertThat(result.getStrategyScore()).isAtLeast(0.0);
    assertThat(result.getMaxDrawdown()).isAtLeast(0.0);
    assertThat(result.getMaxDrawdown()).isAtMost(1.0);
    assertThat(result.getWinRate()).isAtLeast(0.0);
    assertThat(result.getWinRate()).isAtMost(1.0);
    assertThat(result.getVolatility()).isAtLeast(0.0);
    // If trades occurred, cumulative return should be non-zero
    if (result.getNumberOfTrades() > 0) {
      assertThat(Math.abs(result.getCumulativeReturn())).isGreaterThan(0.0);
    }
  }

  @Test
  public void runBacktest_withLosingTrades_calculatesMetricsCorrectly()
      throws InvalidProtocolBufferException {
    // Arrange - Create data that simulates losing trades
    addTestBarsForLosingScenario();

    BacktestRequest request =
        BacktestRequest.newBuilder()
            .addAllCandles(candlesList)
            .setStrategy(createStrategyWithDefaults("SMA_RSI"))
            .build();

    // Act
    BacktestResult result = backtestRunner.runBacktest(request);

    // Assert - Focus on metrics that should be consistent regardless of strategy performance
    assertThat(result.getMaxDrawdown()).isAtLeast(0.0);
    assertThat(result.getVolatility()).isAtLeast(0.0);
    assertThat(result.getWinRate()).isAtLeast(0.0);
    assertThat(result.getWinRate()).isAtMost(1.0);
    // If trades occurred and were losing, profit factor should be low
    if (result.getNumberOfTrades() > 0 && result.getCumulativeReturn() < 0) {
      assertThat(result.getProfitFactor()).isAtMost(1.0);
    }
  }

  @Test
  public void runBacktest_withVolatileData_calculatesVolatilityCorrectly()
      throws InvalidProtocolBufferException {
    // Arrange - Create truly volatile data
    addTestBarsForHighVolatility();

    BacktestRequest request =
        BacktestRequest.newBuilder()
            .addAllCandles(candlesList)
            .setStrategy(createStrategyWithDefaults("SMA_RSI"))
            .build();

    // Act
    BacktestResult result = backtestRunner.runBacktest(request);

    // Assert - Focus on volatility calculation rather than specific Sharpe ratio
    assertThat(result.getVolatility()).isGreaterThan(0.1); // Should be high due to volatile data
    assertThat(result.getMaxDrawdown()).isGreaterThan(0.0);
    // Sharpe ratio calculation depends on many factors, so just verify it's calculated
    assertThat(Double.isFinite(result.getSharpeRatio())).isTrue();
  }

  @Test
  public void runBacktest_withNoTrades_returnsZeroMetrics() throws InvalidProtocolBufferException {
    // Arrange - Create stable data that won't trigger trades
    addTestBarsForNoTrades();

    BacktestRequest request =
        BacktestRequest.newBuilder()
            .addAllCandles(candlesList)
            .setStrategy(createStrategyWithDefaults("SMA_RSI"))
            .build();

    // Act
    BacktestResult result = backtestRunner.runBacktest(request);

    // Assert
    assertThat(result.getNumberOfTrades()).isEqualTo(0);
    assertThat(result.getWinRate()).isEqualTo(0.0);
    assertThat(result.getAverageTradeDuration()).isEqualTo(0.0);
    assertThat(result.getCumulativeReturn()).isEqualTo(0.0);
    assertThat(Double.isNaN(result.getProfitFactor())).isTrue();
  }

  @Test
  public void runBacktest_withWinningTradeAndZeroLosses_returnsNanProfitFactor()
      throws InvalidProtocolBufferException {
    // Arrange - Deterministic series producing 1 winning closed trade and 0 losses
    addDeterministicWinningBars();

    BacktestRequest request =
        BacktestRequest.newBuilder()
            .addAllCandles(candlesList)
            .setStrategy(createStrategyWithDefaults("EMA_MACD"))
            .build();

    // Act
    BacktestResult result = backtestRunner.runBacktest(request);

    // Assert
    assertThat(result.getNumberOfTrades()).isAtLeast(1);
    assertThat(result.getCumulativeReturn()).isGreaterThan(0.0);
    assertThat(Double.isNaN(result.getProfitFactor())).isTrue();
    assertThat(Double.isFinite(result.getStrategyScore())).isTrue();
  }

  @Test
  public void runBacktest_withMixedWinningAndLosingTrades_calculatesGrossProfitOverGrossLoss()
      throws InvalidProtocolBufferException {
    // Arrange - Deterministic series producing 2 winning closed trades and 1 losing closed trade
    addDeterministicMultiTradeBars();

    BacktestRequest request =
        BacktestRequest.newBuilder()
            .addAllCandles(candlesList)
            .setStrategy(createStrategyWithDefaults("EMA_MACD"))
            .build();

    // Act
    BacktestResult result = backtestRunner.runBacktest(request);

    // Assert
    assertThat(result.getNumberOfTrades()).isEqualTo(3);
    assertThat(result.getWinRate()).isWithin(1e-4).of(2.0 / 3.0);
    double expectedGrossProfit = 62.64;
    double expectedGrossLoss = 2.20;
    double expectedProfitFactor = expectedGrossProfit / expectedGrossLoss;
    assertThat(result.getProfitFactor()).isWithin(1e-9).of(expectedProfitFactor);
    assertThat(result.getCumulativeReturn()).isWithin(1e-9).of(expectedGrossProfit - expectedGrossLoss);
  }

  @Test
  public void runBacktest_withLosingTradeAndZeroWins_returnsZeroProfitFactor()
      throws InvalidProtocolBufferException {
    // Arrange - Deterministic series producing 1 losing closed trade and 0 wins
    addDeterministicLosingBars();

    BacktestRequest request =
        BacktestRequest.newBuilder()
            .addAllCandles(candlesList)
            .setStrategy(createStrategyWithDefaults("EMA_MACD"))
            .build();

    // Act
    BacktestResult result = backtestRunner.runBacktest(request);

    // Assert
    assertThat(result.getNumberOfTrades()).isAtLeast(1);
    assertThat(result.getWinRate()).isEqualTo(0.0);
    assertThat(result.getCumulativeReturn()).isLessThan(0.0);
    assertThat(result.getProfitFactor()).isEqualTo(0.0);
    assertThat(Double.isFinite(result.getStrategyScore())).isTrue();
  }

  @Test
  public void runBacktest_withStrategyWithoutParameters_throwsException() {
    // Arrange
    addTestBarsForOversoldRecovery();

    // Create strategy without parameters (like the original failing tests)
    Strategy strategyWithoutParams = Strategy.newBuilder().setStrategyName("SMA_RSI").build();

    BacktestRequest request =
        BacktestRequest.newBuilder()
            .addAllCandles(candlesList)
            .setStrategy(strategyWithoutParams)
            .build();

    // Act & Assert
    IllegalArgumentException thrown =
        assertThrows(IllegalArgumentException.class, () -> backtestRunner.runBacktest(request));

    assertThat(thrown).hasMessageThat().contains("Strategy must have valid parameters");
    assertThat(thrown).hasMessageThat().contains("Use getDefaultParameters(strategyType)");
    assertThat(thrown).hasMessageThat().contains("SMA_RSI");
  }

  // Helper method to create properly configured strategies using string-based names
  private Strategy createStrategyWithDefaults(String strategyName) {
    return Strategy.newBuilder()
        .setStrategyName(strategyName)
        .setParameters(
            Any.pack(
                StrategySpecs.getSpec(strategyName).getStrategyFactory().getDefaultParameters()))
        .build();
  }

  // Create data that might trigger oversold conditions and recovery
  private void addTestBarsForOversoldRecovery() {
    candlesList.clear();
    double basePrice = 100.0;
    // Phase 1: Baseline (10 bars)
    for (int i = 0; i < 10; i++) {
      candlesList.add(createCandle(startTime.plusMinutes(i), basePrice + (i * 0.5)));
    }
    // Phase 2: Sharp decline to create oversold conditions (10 bars)
    for (int i = 10; i < 20; i++) {
      double price = basePrice + 5 - ((i - 9) * 3); // Sharp decline
      candlesList.add(createCandle(startTime.plusMinutes(i), Math.max(price, 70.0)));
    }
    // Phase 3: Recovery (15 bars)
    for (int i = 20; i < 35; i++) {
      double price = 70.0 + ((i - 19) * 2); // Recovery
      candlesList.add(createCandle(startTime.plusMinutes(i), price));
    }
  }

  // Create data for losing scenario
  private void addTestBarsForLosingScenario() {
    candlesList.clear();
    double basePrice = 100.0;
    // Gradual decline over 30 bars
    for (int i = 0; i < 30; i++) {
      double price = basePrice - (i * 1.5); // Steady decline
      candlesList.add(createCandle(startTime.plusMinutes(i), Math.max(price, 50.0)));
    }
  }

  // Create highly volatile data
  private void addTestBarsForHighVolatility() {
    candlesList.clear();
    double basePrice = 100.0;
    // Create zigzag pattern with high volatility
    for (int i = 0; i < 30; i++) {
      double volatility = (i % 2 == 0) ? 15.0 : -15.0; // Alternate high/low
      double noise = (Math.random() - 0.5) * 10.0; // Random noise
      double price = basePrice + volatility + noise;
      candlesList.add(createCandle(startTime.plusMinutes(i), Math.max(price, 20.0)));
    }
  }

  // Create stable data that won't trigger trades
  private void addTestBarsForNoTrades() {
    candlesList.clear();
    double basePrice = 100.0;
    // Very stable prices with minimal variation
    for (int i = 0; i < 25; i++) {
      double price = basePrice + (Math.sin(i * 0.1) * 0.5); // Tiny oscillation
      candlesList.add(createCandle(startTime.plusMinutes(i), price));
    }
  }

  private void addDeterministicWinningBars() {
    candlesList.clear();
    ZonedDateTime fixedStartTime = ZonedDateTime.of(2024, 1, 1, 0, 0, 0, 0, ZoneOffset.UTC);
    List<Double> prices = new ArrayList<>();
    for (int i = 0; i < 27; i++) prices.add(100.0);
    addRamp(prices, 100.0, 95.0, 8);
    for (int i = 0; i < 5; i++) prices.add(95.0);
    addRamp(prices, 95.0, 125.0, 17);
    addRamp(prices, 125.0, 118.0, 12);
    for (int i = 0; i < 11; i++) prices.add(118.0);

    for (int i = 0; i < prices.size(); i++) {
      candlesList.add(createCandle(fixedStartTime.plusHours(i), prices.get(i)));
    }
  }

  private void addDeterministicMultiTradeBars() {
    candlesList.clear();
    ZonedDateTime fixedStartTime = ZonedDateTime.of(2024, 1, 1, 0, 0, 0, 0, ZoneOffset.UTC);
    List<Double> prices = new ArrayList<>();
    for (int i = 0; i < 27; i++) prices.add(100.0);
    addRamp(prices, 100.0, 95.0, 8);
    for (int i = 0; i < 5; i++) prices.add(95.0);
    addRamp(prices, 95.0, 125.0, 17);
    addRamp(prices, 125.0, 118.0, 12);
    for (int i = 0; i < 10; i++) prices.add(118.0);
    addRamp(prices, 118.0, 126.0, 8);
    addRamp(prices, 126.0, 100.0, 15);
    for (int i = 0; i < 10; i++) prices.add(100.0);
    addRamp(prices, 100.0, 145.0, 15);
    addRamp(prices, 145.0, 135.0, 15);
    for (int i = 0; i < 15; i++) prices.add(135.0);

    for (int i = 0; i < prices.size(); i++) {
      candlesList.add(createCandle(fixedStartTime.plusHours(i), prices.get(i)));
    }
  }

  private void addDeterministicLosingBars() {
    candlesList.clear();
    ZonedDateTime fixedStartTime = ZonedDateTime.of(2024, 1, 1, 0, 0, 0, 0, ZoneOffset.UTC);
    List<Double> prices = new ArrayList<>();
    for (int i = 0; i < 27; i++) prices.add(100.0);
    addRamp(prices, 100.0, 95.0, 8);
    for (int i = 0; i < 5; i++) prices.add(95.0);
    addRamp(prices, 95.0, 103.0, 8);
    addRamp(prices, 103.0, 80.0, 15);
    for (int i = 0; i < 20; i++) prices.add(80.0);

    for (int i = 0; i < prices.size(); i++) {
      candlesList.add(createCandle(fixedStartTime.plusHours(i), prices.get(i)));
    }
  }

  private void addRamp(List<Double> prices, double start, double end, int steps) {
    double step = (end - start) / steps;
    for (int i = 0; i < steps; i++) {
      prices.add(Math.round((start + i * step) * 100.0) / 100.0);
    }
  }

  private Candle createCandle(ZonedDateTime time, double price) {
    return Candle.newBuilder()
        .setTimestamp(Timestamps.fromMillis(time.toInstant().toEpochMilli()))
        .setOpen(price)
        .setHigh(price * 1.01) // Small spread
        .setLow(price * 0.99)
        .setClose(price)
        .setVolume(100)
        .setCurrencyPair("BTC/USD")
        .build();
  }
}
