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
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.Strategy;
import com.verlumen.tradestream.strategies.StrategyManager;
import com.verlumen.tradestream.strategies.StrategyType;
import java.time.Duration;
import java.time.Instant;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.BarSeries;

@RunWith(JUnit4.class)
public class BacktestRunnerImplTest {
    @Rule public MockitoRule mockitoRule = MockitoJUnit.rule();

    @Bind
    @Mock
    private StrategyManager mockStrategyManager;

    private List<Candle> candlesList;
    private org.ta4j.core.Strategy ta4jStrategy;
    private ZonedDateTime startTime;

    @Inject private BacktestRunnerImpl backtestRunner;

    @Before
    public void setUp() {
        // Initialize test data
        candlesList = new ArrayList<>();
        startTime = ZonedDateTime.now();

        // Create a simple strategy that enters on bar index 1 and exits on bar index 3
        ta4jStrategy = new BaseStrategy(
            (index, series) -> index == 1, // Entry rule
            (index, series) -> index == 3  // Exit rule
        );
        
        // Setup the mock strategy manager to return our ta4j strategy
        when(mockStrategyManager.createStrategy(
            org.mockito.ArgumentMatchers.any(BarSeries.class),
            org.mockito.ArgumentMatchers.any(StrategyType.class),
            org.mockito.ArgumentMatchers.any(Any.class)))
            .thenReturn(ta4jStrategy);
            
        // Inject our dependencies
        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void runBacktest_withEmptySeries_throwsException() throws InvalidProtocolBufferException {
        // Arrange
        BacktestRequest request = BacktestRequest.newBuilder()
            .addAllCandles(ImmutableList.of()) // Empty candles list
            .setStrategy(Strategy.newBuilder().setType(StrategyType.SMA_RSI).build())
            .build();

        // Act & Assert
        IllegalArgumentException thrown = assertThrows(
            IllegalArgumentException.class,
            () -> backtestRunner.runBacktest(request));
        
        assertThat(thrown).hasMessageThat().contains("Bar series cannot be empty");
    }

    @Test
    public void runBacktest_withValidDataAndStrategy_returnsResults() throws InvalidProtocolBufferException {
        // Arrange
        // Add test data: steadily increasing prices
        addTestBars(100.0, 101.0, 102.0, 103.0, 104.0);

        BacktestRequest request = BacktestRequest.newBuilder()
            .addAllCandles(candlesList)
            .setStrategy(Strategy.newBuilder().setType(StrategyType.SMA_RSI).build())
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
    public void runBacktest_withLosingTrades_calculatesMetricsCorrectly() throws InvalidProtocolBufferException {
        // Arrange
        // Add test data: declining prices
        addTestBars(100.0, 98.0, 95.0, 92.0, 90.0);

        BacktestRequest request = BacktestRequest.newBuilder()
            .addAllCandles(candlesList)
            .setStrategy(Strategy.newBuilder().setType(StrategyType.SMA_RSI).build())
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
    public void runBacktest_withVolatileData_calculatesVolatilityCorrectly() throws InvalidProtocolBufferException {
        // Arrange
        // Add test data: volatile prices
        addTestBars(100.0, 110.0, 95.0, 105.0, 90.0);

        BacktestRequest request = BacktestRequest.newBuilder()
            .addAllCandles(candlesList)
            .setStrategy(Strategy.newBuilder().setType(StrategyType.SMA_RSI).build())
            .build();

        // Act
        BacktestResult result = backtestRunner.runBacktest(request);

        // Assert
        TimeframeResult firstTimeframe = result.getTimeframeResults(0);
        assertThat(firstTimeframe.getVolatility()).isGreaterThan(0.0);
        // We use isWithin() instead of isEqualTo() as calculations might have small differences
        assertThat(firstTimeframe.getSharpeRatio()).isWithin(0.1).of(-41.43383146756991);
    }

    @Test
    public void runBacktest_withNoTrades_returnsZeroMetrics() throws InvalidProtocolBufferException {
        // Arrange
        // Add test data
        addTestBars(100.0, 100.0, 100.0, 100.0, 100.0);

        // Create a different mock for this test that returns a no-trade strategy
        org.ta4j.core.Strategy noTradeStrategy = new BaseStrategy(
            (index, series) -> false,  // Never enter
            (index, series) -> false   // Never exit
        );
        
        // Override mock for this test only
        when(mockStrategyManager.createStrategy(
            org.mockito.ArgumentMatchers.any(BarSeries.class),
            org.mockito.ArgumentMatchers.any(StrategyType.class),
            org.mockito.ArgumentMatchers.any(Any.class)))
            .thenReturn(noTradeStrategy);

        BacktestRequest request = BacktestRequest.newBuilder()
            .addAllCandles(candlesList)
            .setStrategy(Strategy.newBuilder().setType(StrategyType.SMA_RSI).build())
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
        candlesList.clear();
        for (int i = 0; i < prices.length; i++) {
            candlesList.add(createCandle(startTime.plusMinutes(i), prices[i]));
        }
    }

    private Candle createCandle(ZonedDateTime time, double price) {
        return Candle.newBuilder()
            .setTimestamp(Timestamps.fromMillis(time.toInstant().toEpochMilli()))
            .setOpen(price)
            .setHigh(price)
            .setLow(price)
            .setClose(price)
            .setVolume(100)
            .setCurrencyPair("BTC/USD")
            .build();
    }
}
