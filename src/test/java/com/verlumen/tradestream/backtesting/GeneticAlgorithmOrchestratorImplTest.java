package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.backtesting.ParamConfig;
import com.verlumen.tradestream.backtesting.ParamConfigManager;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.StrategyType;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class GeneticAlgorithmOrchestratorImplTest {
    @Rule public MockitoRule mockito = MockitoJUnit.rule();

    @Bind 
    @Mock 
    private BacktestServiceClient mockBacktestServiceClient;

    @Bind
    @Mock
    private ParamConfigManager mockParamConfigManager;

    @Inject
    private GeneticAlgorithmOrchestratorImpl orchestrator;

    private GAOptimizationRequest request;
    private BacktestResult mockBacktestResult;

    @Before
    public void setUp() {
        // Create mock backtest result
        mockBacktestResult = BacktestResult.newBuilder()
            .setOverallScore(0.75)
            .build();

        // Set up mock backtest service
        when(mockBacktestServiceClient.runBacktest(any()))
            .thenReturn(mockBacktestResult);

        // Set up mock param config manager
        when(mockParamConfigManager.getParamConfig(any()))
            .thenReturn(new SmaRsiParamConfig());  // Use a concrete config for testing

        // Create basic valid request
        request = createValidRequest();

        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void runOptimization_withValidRequest_returnsOptimizedParameters() {
        // Arrange
        ArgumentCaptor<BacktestRequest> backtestCaptor = 
            ArgumentCaptor.forClass(BacktestRequest.class);

        // Act
        BestStrategyResponse response = orchestrator.runOptimization(request);

        // Assert
        verify(mockBacktestServiceClient).runBacktest(backtestCaptor.capture());
        
        BacktestRequest capturedRequest = backtestCaptor.getValue();
        assertThat(capturedRequest.getStrategyType()).isEqualTo(request.getStrategyType());
        assertThat(capturedRequest.getCandlesList()).isEqualTo(request.getCandlesList());
        
        assertThat(response.getBestScore()).isEqualTo(mockBacktestResult.getOverallScore());
        assertThat(response.getBestStrategyParameters()).isNotNull();
    }

    @Test
    public void runOptimization_withEmptyCandles_throwsException() {
        // Arrange
        request = GAOptimizationRequest.newBuilder()
            .setStrategyType(StrategyType.SMA_RSI)
            .setMaxGenerations(10)
            .setPopulationSize(20)
            .build();

        // Act & Assert
        IllegalArgumentException thrown = assertThrows(
            IllegalArgumentException.class,
            () -> orchestrator.runOptimization(request));
        
        assertThat(thrown).hasMessageThat().contains("Candles list cannot be empty");
    }

    @Test
    public void runOptimization_withCustomGenerationsAndPopulation_usesCustomValues() {
        // Arrange
        int customGenerations = 5;
        int customPopulation = 10;
        
        request = request.toBuilder()
            .setMaxGenerations(customGenerations)
            .setPopulationSize(customPopulation)
            .build();

        // Act
        BestStrategyResponse response = orchestrator.runOptimization(request);

        // Assert
        verify(mockBacktestServiceClient).runBacktest(any());
        assertThat(response.getBestStrategyParameters()).isNotNull();
    }

    @Test
    public void runOptimization_withUnsupportedStrategy_throwsException() {
        // Arrange
        request = request.toBuilder()
            .setStrategyType(StrategyType.UNRECOGNIZED)
            .build();

        // Act & Assert
        IllegalArgumentException thrown = assertThrows(
            IllegalArgumentException.class,
            () -> orchestrator.runOptimization(request));
        
        assertThat(thrown).hasMessageThat()
            .contains("Unsupported strategy type: UNRECOGNIZED");
    }

    private GAOptimizationRequest createValidRequest() {
        return GAOptimizationRequest.newBuilder()
            .setStrategyType(StrategyType.SMA_RSI)
            .addAllCandles(createTestCandles())
            .setMaxGenerations(10)
            .setPopulationSize(20)
            .build();
    }

    private List<Candle> createTestCandles() {
        List<Candle> candles = new ArrayList<>();
        for (int i = 0; i < 10; i++) {
            candles.add(createCandle(i + 1.0));
        }
        return candles;
    }

    private Candle createCandle(double price) {
        return Candle.newBuilder()
            .setTimestamp(Instant.now().toEpochMilli())
            .setOpen(price)
            .setHigh(price + 1)
            .setLow(price - 1)
            .setClose(price)
            .setVolume(1000)
            .build();
    }
}
