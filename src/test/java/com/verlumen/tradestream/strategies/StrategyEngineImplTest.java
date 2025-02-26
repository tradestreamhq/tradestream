package com.verlumen.tradestream.strategies;

import static com.google.common.truth.Truth.assertThat;
import static com.google.protobuf.util.Timestamps.fromMillis;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.backtesting.BestStrategyResponse;
import com.verlumen.tradestream.backtesting.GAOptimizationRequest;
import com.verlumen.tradestream.backtesting.GeneticAlgorithmOrchestrator;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.signals.TradeSignal;
import com.verlumen.tradestream.signals.TradeSignalPublisher;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

@RunWith(JUnit4.class)
public class StrategyEngineImplTest {
    @Rule public MockitoRule mockito = MockitoJUnit.rule();

    @Mock @Bind private GeneticAlgorithmOrchestrator mockGeneticAlgorithmOrchestrator;
    @Mock @Bind private StrategyManager mockStrategyManager;
    @Mock @Bind private TradeSignalPublisher mockSignalPublisher;
    @Mock @Bind private Strategy mockStrategy;
    @Mock @Bind private CandleBuffer mockCandleBuffer;
    @Mock private BarSeries mockBarSeries;

    @Inject
    private StrategyEngineImpl engine;

    @Before
    public void setUp() throws InvalidProtocolBufferException {
        // Mock returns
        when(mockStrategyManager.getStrategyTypes())
            .thenReturn(ImmutableList.of(StrategyType.SMA_RSI, StrategyType.EMA_MACD));
        when(mockStrategyManager.createStrategy(any(), any(), any())).thenReturn(mockStrategy);
        when(mockCandleBuffer.toBarSeries()).thenReturn(mockBarSeries);
        when(mockCandleBuffer.getCandles()).thenReturn(ImmutableList.of());

        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }


    @Test
    public void handleCandle_withValidCandle_updatesBuffer() {
        // Arrange
        Candle candle = createTestCandle(100.0);

        // Act
        engine.handleCandle(candle);

        // Assert
        verify(mockCandleBuffer).add(candle);
    }

    @Test
    public void handleCandle_withSellSignal_triggersOptimization() {
        // Arrange
        setupOptimizationScenario(); // Mocks the SELL condition and stubs bestResponse
        Candle candle = createTestCandle(100.0);

        // Act
        engine.handleCandle(candle);

        // Assert
        // Instead of verify(..., times(1)), expect times(2)
        verify(mockGeneticAlgorithmOrchestrator, times(2)).requestOptimization(any(GAOptimizationRequest.class));
    }

    @Test
    public void handleCandle_withBuyConditions_generatesAndPublishesBuySignal() {
        // Arrange
        when(mockStrategy.shouldEnter(any(Integer.class))).thenReturn(true);
        Candle candle = createTestCandle(100.0);

        // Act
        engine.handleCandle(candle);

        // Assert
        ArgumentCaptor<TradeSignal> signalCaptor = ArgumentCaptor.forClass(TradeSignal.class);
        verify(mockSignalPublisher).publish(signalCaptor.capture());

        TradeSignal capturedSignal = signalCaptor.getValue();
        assertThat(capturedSignal.getType()).isEqualTo(TradeSignal.TradeSignalType.BUY);
        assertThat(capturedSignal.getPrice()).isEqualTo(100.0);
    }

    @Test
    public void handleCandle_withSellConditions_generatesAndPublishesSellSignal() {
        // Arrange
        when(mockStrategy.shouldExit(any(Integer.class))).thenReturn(true);
        Candle candle = createTestCandle(100.0);

        // Act
        engine.handleCandle(candle);

        // Assert
        ArgumentCaptor<TradeSignal> signalCaptor = ArgumentCaptor.forClass(TradeSignal.class);
        verify(mockSignalPublisher).publish(signalCaptor.capture());

        TradeSignal capturedSignal = signalCaptor.getValue();
        assertThat(capturedSignal.getType()).isEqualTo(TradeSignal.TradeSignalType.SELL);
        assertThat(capturedSignal.getPrice()).isEqualTo(100.0);
    }

    @Test
    public void optimizeStrategy_selectsBestPerformingStrategy() throws InvalidProtocolBufferException {
        // Arrange
        BestStrategyResponse bestResponse = BestStrategyResponse.newBuilder()
            .setBestScore(0.95)
            .setBestStrategyParameters(Any.getDefaultInstance())
            .build();
        when(mockGeneticAlgorithmOrchestrator.requestOptimization(any())).thenReturn(bestResponse);

        // Act
        engine.optimizeStrategy();

        // Assert
        verify(mockStrategyManager).createStrategy(any(), any(), any());
        verify(mockGeneticAlgorithmOrchestrator, times(2)).requestOptimization(any());
    }

    @Test
    public void getCurrentStrategy_afterOptimization_returnsUpdatedStrategy() throws InvalidProtocolBufferException {
        // Arrange
        optimizeStrategy_selectsBestPerformingStrategy(); // Reuse optimization test

        // Act
        Strategy result = engine.getCurrentStrategy();

        // Assert
        assertThat(result).isSameInstanceAs(mockStrategy);
    }

    private void setupOptimizationScenario() {
        // Setup conditions that trigger optimization (e.g., SELL signal)
        when(mockStrategy.shouldExit(any(Integer.class))).thenReturn(true);
        BestStrategyResponse bestResponse = BestStrategyResponse.newBuilder()
            .setBestScore(0.95)
            .setBestStrategyParameters(Any.getDefaultInstance())
            .build();
        when(mockGeneticAlgorithmOrchestrator.requestOptimization(any())).thenReturn(bestResponse);
    }

    private Candle createTestCandle(double price) {
        long epochMillis = System.currentTimeMillis();
        return Candle.newBuilder()
            .setTimestamp(fromMillis(epochMillis))
            .setOpen(price)
            .setHigh(price + 1)
            .setLow(price - 1)
            .setClose(price)
            .setVolume(1000)
            .setCurrencyPair("BTC/USD")
            .build();
    }
}
