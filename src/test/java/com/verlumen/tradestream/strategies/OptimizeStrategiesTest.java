package com.verlumen.tradestream.strategies;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.google.protobuf.Timestamp;
import com.verlumen.tradestream.backtesting.BestStrategyResponse;
import com.verlumen.tradestream.backtesting.GAOptimizationRequest;
import com.verlumen.tradestream.backtesting.GeneticAlgorithmOrchestrator;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.ta4j.BarSeriesBuilder;
import java.time.Instant;
import java.util.List;
import org.apache.beam.sdk.coders.KvCoder;
import org.apache.beam.sdk.coders.SerializableCoder;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnitRunner;
import org.ta4j.core.BarSeries;
import org.unitils.inject.annotation.TestedObject;
import org.unitils.inject.util.BoundFieldModule;

@RunWith(MockitoJUnitRunner.class)
public class OptimizeStrategiesTest {
  private static final String TEST_KEY = "BTC-USD";
  private static final ImmutableList<StrategyType> STRATEGY_TYPES =
      ImmutableList.of(StrategyType.SMA_RSI, StrategyType.SMA_EMA_CROSSOVER);

  @Rule
  public final TestPipeline pipeline = TestPipeline.create();

  @Mock private GeneticAlgorithmOrchestrator mockOrchestrator;
  @Mock private StrategyState.Factory mockStateFactory;
  @Mock private StrategyState mockInitialState;
  @Mock private StrategyState mockOptimizedState;
  @Mock private BarSeries mockBarSeries;
  @Inject private OptimizeStrategies optimizeStrategies;

  @Before
  public void setUp() {
    // Create and inject test dependencies using BoundFieldModule
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    
    // Mock bar series builder to always return our mock bar series
    BarSeriesBuilder.setSeriesFactoryForTesting(() -> mockBarSeries);
    
    // Setup mock states
    when(mockStateFactory.create()).thenReturn(mockInitialState);
    when(mockInitialState.getStrategyTypes()).thenReturn(STRATEGY_TYPES);
    when(mockInitialState.selectBestStrategy(mockBarSeries)).thenReturn(mockOptimizedState);
    
    // Setup response for optimization requests
    BestStrategyResponse mockResponse = BestStrategyResponse.newBuilder()
        .setStrategyType(StrategyType.SMA_RSI)
        .setBestScore(0.75)
        .setBestStrategyParameters(Any.getDefaultInstance())
        .build();
    when(mockOrchestrator.runOptimization(any(GAOptimizationRequest.class)))
        .thenReturn(mockResponse);
  }

  @Test
  public void transform_withEmptyInput_shouldProduceEmptyOutput() {
    // Arrange - Create empty input
    PCollection<KV<String, ImmutableList<Candle>>> input = pipeline
        .apply("CreateEmptyInput", Create.empty(
            KvCoder.of(StringUtf8Coder.of(), 
                       SerializableCoder.of(ImmutableList.class))));
    
    // Act - Apply our transform
    PCollection<KV<String, StrategyState>> output = input.apply(optimizeStrategies);
    
    // Assert - Verify empty output
    PAssert.that(output).empty();
    pipeline.run();
  }

  @Test
  public void transform_withEmptyCandles_shouldProduceNoOutput() {
    // Arrange - Create input with empty candle list
    PCollection<KV<String, ImmutableList<Candle>>> input = pipeline
        .apply("CreateEmptyCandles", Create.of(
            KV.of(TEST_KEY, ImmutableList.<Candle>of())));
    
    // Act - Apply our transform
    PCollection<KV<String, StrategyState>> output = input.apply(optimizeStrategies);
    
    // Assert - Verify empty output
    PAssert.that(output).empty();
    pipeline.run();
  }

  @Test
  public void transform_withValidCandlesAndNoExistingState_shouldProduceOptimizedState() {
    // Arrange
    ImmutableList<Candle> candles = createSampleCandles(10);
    PCollection<KV<String, ImmutableList<Candle>>> input = pipeline
        .apply("CreateValidInput", Create.of(KV.of(TEST_KEY, candles)));
    
    // Act
    PCollection<KV<String, StrategyState>> output = input.apply(optimizeStrategies);
    
    // Assert - Verify output contains optimized state for our key
    PAssert.that(output).containsInAnyOrder(
        KV.of(TEST_KEY, mockOptimizedState));
    pipeline.run();
    
    // Verify optimization was performed for each strategy type
    ArgumentCaptor<GAOptimizationRequest> requestCaptor = ArgumentCaptor.forClass(GAOptimizationRequest.class);
    verify(mockOrchestrator, times(2)).runOptimization(requestCaptor.capture());
    
    List<GAOptimizationRequest> capturedRequests = requestCaptor.getAllValues();
    assertEquals(2, capturedRequests.size());
    
    // Verify first strategy type was optimized
    GAOptimizationRequest firstRequest = capturedRequests.get(0);
    assertEquals(STRATEGY_TYPES.get(0), firstRequest.getStrategyType());
    assertEquals(candles, firstRequest.getCandlesList());
    
    // Verify second strategy type was optimized
    GAOptimizationRequest secondRequest = capturedRequests.get(1);
    assertEquals(STRATEGY_TYPES.get(1), secondRequest.getStrategyType());
    assertEquals(candles, secondRequest.getCandlesList());
    
    // Verify state was initialized, records updated, and best strategy selected
    verify(mockStateFactory).create();
    verify(mockInitialState, times(2)).updateRecord(any(StrategyType.class), any(Any.class), any(Double.class));
    verify(mockInitialState).selectBestStrategy(mockBarSeries);
  }

  @Test
  public void transform_withMultipleInputs_shouldProcessEachKeyIndependently() {
    // Arrange - Create input with multiple keys
    String key1 = "BTC-USD";
    String key2 = "ETH-USD";
    ImmutableList<Candle> candles1 = createSampleCandles(5);
    ImmutableList<Candle> candles2 = createSampleCandles(7);
    
    PCollection<KV<String, ImmutableList<Candle>>> input = pipeline
        .apply("CreateMultiKeyInput", Create.of(
            KV.of(key1, candles1),
            KV.of(key2, candles2)));
    
    // Create a second optimized state for the second key
    StrategyState mockOptimizedState2 = mock(StrategyState.class);
    when(mockInitialState.selectBestStrategy(mockBarSeries))
        .thenReturn(mockOptimizedState)  // First call returns first state
        .thenReturn(mockOptimizedState2); // Second call returns second state
    
    // Act
    PCollection<KV<String, StrategyState>> output = input.apply(optimizeStrategies);
    
    // Assert - Verify output contains both optimized states
    PAssert.that(output).containsInAnyOrder(
        KV.of(key1, mockOptimizedState),
        KV.of(key2, mockOptimizedState2));
    pipeline.run();
    
    // Verify optimization was performed for each key
    verify(mockOrchestrator, times(4)).runOptimization(any(GAOptimizationRequest.class));
  }

  @Test
  public void transform_withOptimizationError_shouldHandleGracefully() {
    // Arrange
    ImmutableList<Candle> candles = createSampleCandles(3);
    PCollection<KV<String, ImmutableList<Candle>>> input = pipeline
        .apply("CreateValidInput", Create.of(KV.of(TEST_KEY, candles)));
    
    // Setup first optimization to throw exception, second to succeed
    when(mockOrchestrator.runOptimization(any(GAOptimizationRequest.class)))
        .thenThrow(new RuntimeException("Optimization failed"))
        .thenReturn(BestStrategyResponse.newBuilder()
            .setStrategyType(StrategyType.SMA_EMA_CROSSOVER)
            .setBestStrategyParameters(Any.getDefaultInstance())
            .setBestScore(0.65)
            .build());
    
    // Act
    PCollection<KV<String, StrategyState>> output = input.apply(optimizeStrategies);
    
    // Assert - Verify we still get output despite the error
    PAssert.that(output).containsInAnyOrder(
        KV.of(TEST_KEY, mockOptimizedState));
    pipeline.run();
    
    // Verify only one strategy type was successfully optimized
    verify(mockInitialState, times(1)).updateRecord(
        eq(StrategyType.SMA_EMA_CROSSOVER), 
        any(Any.class), 
        eq(0.65));
  }

  // Helper methods
  private ImmutableList<Candle> createSampleCandles(int count) {
    ImmutableList.Builder<Candle> builder = ImmutableList.builder();
    long baseTimestamp = Instant.now().getEpochSecond();
    
    for (int i = 0; i < count; i++) {
      Timestamp timestamp = Timestamp.newBuilder()
          .setSeconds(baseTimestamp + (i * 60)) // One minute intervals
          .build();
          
      Candle candle = Candle.newBuilder()
          .setTimestamp(timestamp)
          .setOpen(1000.0 + i)
          .setHigh(1010.0 + i)
          .setLow(990.0 + i)
          .setClose(1005.0 + i)
          .setVolume(100.0 + i)
          .build();
          
      builder.add(candle);
    }
    
    return builder.build();
  }
  
  // Stub out the BarSeriesBuilder for testing
  private static class BarSeriesBuilder {
    private static SeriesFactory seriesFactory;
    
    static void setSeriesFactoryForTesting(SeriesFactory factory) {
      seriesFactory = factory;
    }
    
    static BarSeries createBarSeries(ImmutableList<Candle> candles) {
      return seriesFactory.createSeries();
    }
    
    interface SeriesFactory {
      BarSeries createSeries();
    }
  }
}
