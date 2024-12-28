package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.google.protobuf.util.JsonFormat;
import com.google.common.collect.Range;
import com.verlumen.tradestream.backtesting.params.ChromosomeSpec;
import com.verlumen.tradestream.backtesting.params.ParamConfig;
import com.verlumen.tradestream.backtesting.params.ParamConfigManager;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.NumericChromosome;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class GeneticAlgorithmOrchestratorImplTest {
  @Rule
  public MockitoRule mockito = MockitoJUnit.rule();

  @Bind @Mock
  private BacktestServiceClient mockBacktestServiceClient;

  @Bind @Mock
  private ParamConfigManager mockParamConfigManager;

  @Bind @Mock
  private ParamConfig mockParamConfig;

  @Inject
  private GeneticAlgorithmOrchestratorImpl orchestrator;

  private GAOptimizationRequest request;
  private BacktestResult mockBacktestResult;

  @Before
  public void setUp() {
    // Create a mock backtest result
    mockBacktestResult = BacktestResult.newBuilder().setOverallScore(0.75).build();

    // Stub the BacktestServiceClient
    when(mockBacktestServiceClient.runBacktest(any()))
        .thenReturn(mockBacktestResult);

    // Return at least one ChromosomeSpec so Jenetics doesn't get an empty list
    when(mockParamConfig.getChromosomeSpecs())
        .thenReturn(createMockChromosomeSpecs());

    // Return a dummy Any proto when createParameters(...) is called
    when(mockParamConfig.createParameters(any()))
        .thenReturn(Any.getDefaultInstance());

    // Have the ParamConfigManager return our mocked ParamConfig
    when(mockParamConfigManager.getParamConfig(any()))
        .thenReturn(mockParamConfig);

    // Build a basic valid request
    request = createValidRequest();

    // Inject all @Bind fields via Guice
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }

  @Test
  public void runOptimization_withValidRequest_returnsOptimizedParameters() {
    // Arrange
    ArgumentCaptor<BacktestRequest> backtestCaptor = ArgumentCaptor.forClass(BacktestRequest.class);

    // Act
    BestStrategyResponse response = orchestrator.runOptimization(request);

    // Assert
    verify(mockBacktestServiceClient).runBacktest(backtestCaptor.capture());
    BacktestRequest capturedRequest = backtestCaptor.getValue();

    assertThat(capturedRequest.getStrategyType()).isEqualTo(request.getStrategyType());
    assertThat(capturedRequest.getCandlesList()).isEqualTo(request.getCandlesList());
    assertThat(response.getBestScore()).isEqualTo(mockBacktestResult.getOverallScore());
    assertThat(response.hasBestStrategyParameters()).isTrue();
  }

  @Test
  public void runOptimization_withEmptyCandles_throwsException() {
    // Arrange
    GAOptimizationRequest emptyCandleRequest = GAOptimizationRequest.newBuilder()
        .setStrategyType(StrategyType.SMA_RSI)
        .setMaxGenerations(10)
        .setPopulationSize(20)
        // Notice: no candles here
        .build();

    // Act & Assert
    IllegalArgumentException thrown = assertThrows(
        IllegalArgumentException.class,
        () -> orchestrator.runOptimization(emptyCandleRequest));

    assertThat(thrown).hasMessageThat().contains("Candles list cannot be empty");
  }

  @Test
  public void runOptimization_withCustomGenerationsAndPopulation_usesCustomValues() {
    // Arrange
    int customGenerations = 5;
    int customPopulation = 10;

    GAOptimizationRequest customRequest = request.toBuilder()
        .setMaxGenerations(customGenerations)
        .setPopulationSize(customPopulation)
        .build();

    // Act
    BestStrategyResponse response = orchestrator.runOptimization(customRequest);

    // Assert
    verify(mockBacktestServiceClient).runBacktest(any());
    assertThat(response.hasBestStrategyParameters()).isTrue();
  }

  /**
  * Return at least one ChromosomeSpec so Jenetics doesn't get an empty list.
  * Below is a minimal example that sets a numeric range [1..10].
  */
  private ImmutableList<ChromosomeSpec<?>> createMockChromosomeSpecs() {
      // Use actual implementation rather than trying to mock
      ChromosomeSpec<?> spec = new DoubleChromosomeSpec(Range.closed(1.0, 10.0));
      return ImmutableList.of(spec);
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
