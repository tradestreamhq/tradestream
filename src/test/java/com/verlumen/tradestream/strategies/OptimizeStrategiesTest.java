package com.verlumen.tradestream.strategies;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.verlumen.tradestream.backtesting.BestStrategyResponse;
import com.verlumen.tradestream.backtesting.GAOptimizationRequest;
import com.verlumen.tradestream.backtesting.GeneticAlgorithmOrchestrator;
import com.verlumen.tradestream.marketdata.Candle;
import org.apache.beam.sdk.coders.Coder;
import org.apache.beam.sdk.coders.CoderRegistry;
import org.apache.beam.sdk.coders.KvCoder;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnitRunner;
import  org.apache.beam.sdk.coders.ListCoder;
import org.apache.beam.sdk.values.TypeDescriptors;
import org.apache.beam.sdk.values.TypeDescriptor;
import org.apache.beam.sdk.coders.SerializableCoder;

@RunWith(MockitoJUnitRunner.class)
public class OptimizeStrategiesTest {

  @Rule public final TestPipeline pipeline = TestPipeline.create();

  @Mock @Bind private GeneticAlgorithmOrchestrator mockOrchestrator;
  @Mock @Bind private StrategyState.Factory mockStateFactory;
  @Mock @Bind private StrategyState mockOptimizedState;

  @Captor ArgumentCaptor<GAOptimizationRequest> gaRequestCaptor;

  @Inject private OptimizeStrategies optimizeStrategies;

  @Before
  public void setUp() {
      Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
      when(mockStateFactory.create()).thenReturn(mockOptimizedState);
  }

  private <K, V> KvCoder<K, V> getKvCoder(Coder<K> keyCoder, Coder<V> valueCoder) {
      return KvCoder.of(keyCoder, valueCoder);
  }

  @Test
  public void expand_emptyCandleList_doesNotCallOrchestrator() {
    // Arrange
    PCollection<KV<String, ImmutableList<Candle>>> input =
        pipeline.apply("CreateEmptyInput", Create.empty(
              getKvCoder(StringUtf8Coder.of(), SerializableCoder.of(new TypeDescriptor<ImmutableList<Candle>>() {})) // Use TypeDescriptor
        ));

      // Act
      PCollection<KV<String, StrategyState>> output = input.apply(optimizeStrategies);

    // Assert (using PAssert to verify no output, and Mockito to check for interactions)
    PAssert.that(output).empty();
    pipeline.run();

    // Verify that the orchestrator was never called.
    verify(mockOrchestrator, org.mockito.Mockito.never()).runOptimization(any());
  }

  @Test
  public void expand_nonEmptyCandleList_callsOrchestratorAndOutputsState() throws Exception {
    // Arrange
    String testKey = "testKey";
    Candle candle1 = Candle.newBuilder().setOpen(10).setClose(12).build();
    Candle candle2 = Candle.newBuilder().setOpen(12).setClose(11).build();

    ImmutableList<Candle> candles = ImmutableList.of(candle1, candle2);

        PCollection<KV<String, ImmutableList<Candle>>> input =
                pipeline.apply(
                        "CreateInput",
                        Create.of(KV.of(testKey, candles))
                                .withCoder(getKvCoder(StringUtf8Coder.of(), SerializableCoder.of(new TypeDescriptor<ImmutableList<Candle>>() {})))); // Use TypeDescriptor


    BestStrategyResponse mockResponse =
        BestStrategyResponse.newBuilder()
            .setBestStrategyParameters(Any.getDefaultInstance())
            .setBestScore(0.8)
            .build();

    when(mockOrchestrator.runOptimization(gaRequestCaptor.capture())).thenReturn(mockResponse);
    when(mockOptimizedState.getStrategyTypes()).thenReturn(ImmutableList.of(StrategyType.SMA_RSI));

    // Act
    PCollection<KV<String, StrategyState>> output = input.apply(optimizeStrategies);

    // Assert
    PAssert.that(output).containsInAnyOrder(KV.of(testKey, mockOptimizedState));
    pipeline.run();

    verify(mockOrchestrator).runOptimization(any(GAOptimizationRequest.class));
    GAOptimizationRequest actualRequest = gaRequestCaptor.getValue();
    assertThat(actualRequest.getCandlesList()).containsExactlyElementsIn(candles).inOrder();
    assertThat(actualRequest.getStrategyType()).isEqualTo(StrategyType.SMA_RSI); // Check strategy type
  }

  @Test
  public void expand_multipleStrategies_callsOrchestratorForEachStrategy() throws Exception {
    // Arrange
    String testKey = "testKey";
    ImmutableList<Candle> candles = ImmutableList.of(Candle.newBuilder().build());
      PCollection<KV<String, ImmutableList<Candle>>> input =
              pipeline.apply(
                      "CreateInput",
                      Create.of(KV.of(testKey, candles))
                              .withCoder(getKvCoder(StringUtf8Coder.of(), SerializableCoder.of(new TypeDescriptor<ImmutableList<Candle>>() {}))));  // Use TypeDescriptor

    BestStrategyResponse mockResponse1 = BestStrategyResponse.newBuilder().setBestScore(0.8).build();
    BestStrategyResponse mockResponse2 = BestStrategyResponse.newBuilder().setBestScore(0.9).build();

      StrategyState mockOptimizedState2 = mock(StrategyState.class);
      when(mockStateFactory.create()).thenReturn(mockOptimizedState2);


      when(mockOrchestrator.runOptimization(any(GAOptimizationRequest.class)))
              .thenReturn(mockResponse1).thenReturn(mockResponse2);  //Return different responses for subsequent calls.

    when(mockOptimizedState2.getStrategyTypes()).thenReturn(ImmutableList.of(StrategyType.SMA_RSI, StrategyType.SMA_EMA_CROSSOVER));


      // Act
    PCollection<KV<String, StrategyState>> output = input.apply(optimizeStrategies);

    // Assert
      PAssert.that(output).containsInAnyOrder(KV.of(testKey, mockOptimizedState2));
      pipeline.run();

    verify(mockOrchestrator, org.mockito.Mockito.times(2)).runOptimization(any(GAOptimizationRequest.class));  // Verify called twice.
  }
}
