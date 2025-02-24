package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.StrategyType;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;
import org.ta4j.core.Bar;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Strategy;
import org.ta4j.core.Trade;

@RunWith(JUnit4.class)
public class BacktestRunnerImplTest {
    @Rule public MockitoRule mockitoRule = MockitoJUnit.rule();

    private ImmutableList<Candle> candles;
    private Strategy strategy;
    private ZonedDateTime startTime;

    @Inject private BacktestRunnerImpl backtestRunner;

    @Before
    public void setUp() {
        Guice.createInjector().injectMembers(this);

        // Initialize test data
        candles = ImmutableList.of();
        startTime = ZonedDateTime.now();

        // Create a simple strategy that enters on bar index 1 and exits on bar index 3
        strategy = new BaseStrategy(
            (index, series) -> index == 1, // Entry rule
            (index, series) -> index == 3  // Exit rule
        );
    }

    @Test
    public void runBacktest_withEmptySeries_throwsException() {
        // Arrange
        BacktestRequest request = BacktestRequest.newBuilder()
            .addAllCandles(candles)
            .setStrategyType(StrategyType.SMA_RSI)
            .build();

        // Act & Assert
        IllegalArgumentException thrown = assertThrows(
            IllegalArgumentException.class,
            () -> backtestRunner.runBacktest(request));
        
        assertThat(thrown).hasMessageThat().contains("Bar series cannot be empty");
    }

    @Test
    public void runBacktest_withValidDataAndStrategy_returnsResults() throws Exception {
        // Arrange
        // Add test data: steadily increasing prices
        addTestBars(100.0, 101.0, 102.0, 103.0, 104.0);

        BacktestRequest request = BacktestRequest.newBuilder()
            .addAllCandles(candles)
            .setStrategyType(StrategyType.SMA_RSI)
            .build();

        // Act
        BacktestResult result = backtestRunner.runBacktest(request);

        // Assert
        assertThat(result.getTimeframeResultsCount()).isGreaterThan(0);
        assertThat(result.getOverallScore()).isGreaterThan(0.0);

        // Check first timeframe result
        TimeframeResult firstTimeframe = result.getTimeframeResults(0);
        assertThat(firstTimeframe.getCumulativeReturn()).isGreaterThan(0.0);
        assertThat(firstTimeframe.getNumberOfTrades()).isGreaterThan(0);
        assertThat(firstTimeframe.getMaxDrawdown()).isAtLeast(0.0);
        assertThat(firstTimeframe.getMaxDrawdown()).isAtMost(1.0);
        assertThat(firstTimeframe.getWinRate()).isAtLeast(0.0);
        assertThat(firstTimeframe.getWinRate()).isAtMost(1.0);
    }

    @Test
    public void runBacktest_withLosingTrades_calculatesMetricsCorrectly() {
        // Arrange
        // Add test data: declining prices
        addTestBars(100.0, 98.0, 95.0, 92.0, 90.0);

        BacktestRequest request = BacktestRequest.newBuilder()
            .addAllCandles(candles)
            .setStrategyType(StrategyType.SMA_RSI)
            .build();

        // Act
        BacktestResult result = backtestRunner.runBacktest(request);

        // Assert
        TimeframeResult firstTimeframe = result.getTimeframeResults(0);
        assertThat(firstTimeframe.getCumulativeReturn()).isLessThan(0.0);
        assertThat(firstTimeframe.getMaxDrawdown()).isGreaterThan(0.0);
        assertThat(firstTimeframe.getProfitFactor()).isAtMost(1.0);
    }

    @Test
    public void runBacktest_withVolatileData_calculatesVolatilityCorrectly() throws Exception {
        // Arrange
        // Add test data: volatile prices
        addTestBars(100.0, 110.0, 95.0, 105.0, 90.0);

        BacktestRequest request = BacktestRequest.newBuilder()
            .addAllCandles(candles)
            .setStrategyType(StrategyType.SMA_RSI)
            .build();

        // Act
        BacktestResult result = backtestRunner.runBacktest(request);

        // Assert
        TimeframeResult firstTimeframe = result.getTimeframeResults(0);
        assertThat(firstTimeframe.getVolatility()).isGreaterThan(0.0);
        assertThat(firstTimeframe.getSharpeRatio()).isEqualTo(-41.43383146756991);
    }

    @Test
    public void runBacktest_withNoTrades_returnsZeroMetrics() throws Exception {
        // Arrange
        // Add test data
        addTestBars(100.0, 100.0, 100.0, 100.0, 100.0);

        // Create strategy that never trades
        Strategy noTradeStrategy = new BaseStrategy(
            (index, series) -> false,  // Never enter
            (index, series) -> false   // Never exit
        );

        BacktestRequest request = BacktestRequest.newBuilder()
            .addAllCandles(candles)
            .setStrategy(noTradeStrategy)
            .setStrategyType(StrategyType.SMA_RSI)
            .build();

        // Act
        BacktestResult result = backtestRunner.runBacktest(request);

        // Assert
        TimeframeResult firstTimeframe = result.getTimeframeResults(0);
        assertThat(firstTimeframe.getNumberOfTrades()).isEqualTo(0);
        assertThat(firstTimeframe.getWinRate()).isEqualTo(0.0);
        assertThat(firstTimeframe.getAverageTradeDuration()).isEqualTo(0.0);
    }

    private void addTestBars(double... prices) {
        for (int i = 0; i < prices.length; i++) {
            series.addBar(createBar(startTime.plusMinutes(i), prices[i]));
        }
    }

    private Bar createBar(ZonedDateTime time, double price) {
        return new BaseBar(
            Duration.ofMinutes(1),
            time,
            price,  // open
            price,  // high 
            price,  // low
            price,  // close
            100.0   // volume
        );
    }
}
