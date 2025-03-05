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
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.backtesting.BestStrategyResponse;
import com.verlumen.tradestream.backtesting.GAOptimizationRequest;
import com.verlumen.tradestream.backtesting.GeneticAlgorithmOrchestrator;
import com.verlumen.tradestream.marketdata.Candle;
import java.io.Serializable;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.apache.beam.sdk.coders.KvCoder;
import org.apache.beam.sdk.coders.SerializableCoder;
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
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Strategy;
import org.ta4j.core.rules.BooleanRule;

@RunWith(MockitoJUnitRunner.class)
public class OptimizeStrategiesTest {

  @Rule public final TestPipeline pipeline = TestPipeline.create();

  @Mock @Bind private GeneticAlgorithmOrchestrator mockOrchestrator;

    // Use a Fake instead of a Mock for StrategyState.Factory
    @Bind
    private StrategyState.Factory mockStateFactory = new FakeStrategyStateFactory();

  @Captor ArgumentCaptor<GAOptimizationRequest> gaRequestCaptor;

  @Inject private OptimizeStrategies optimizeStrategies;

  @Before
  public void setUp() {
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }

  private <K, V> KvCoder<K, V> getKvCoder(
      org.apache.beam.sdk.coders.Coder<K> keyCoder,
      org.apache.beam.sdk.coders.Coder<V> valueCoder) {
    return KvCoder.of(keyCoder, valueCoder);
  }

  @Test
  public void expand_emptyCandleList_doesNotCallOrchestrator() {
    // Arrange
    PCollection<KV<String, ImmutableList<Candle>>> input =
        pipeline.apply(
            "CreateEmptyInput",
            Create.empty(
                getKvCoder(
                    StringUtf8Coder.of(),
                    SerializableCoder.of(
                        (Class<ImmutableList<Candle>>) (Class<?>) ImmutableList.class))));

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
                    .withCoder(
                        getKvCoder(
                            StringUtf8Coder.of(),
                            SerializableCoder.of(
                                (Class<ImmutableList<Candle>>) (Class<?>) ImmutableList.class))));

        // Use the same expected response for all calls
        BestStrategyResponse mockResponse =
            BestStrategyResponse.newBuilder()
                .setBestStrategyParameters(Any.getDefaultInstance())
                .setBestScore(0.8)
                .build();

        when(mockOrchestrator.runOptimization(gaRequestCaptor.capture())).thenReturn(mockResponse);

        // Act
        PCollection<KV<String, StrategyState>> output = input.apply(optimizeStrategies);

        // Assert: Use PAssert to check the contents of the output PCollection
        PAssert.that(output)
            .satisfies(
                iterable -> {
                  KV<String, StrategyState> element = iterable.iterator().next();
                  assertThat(element.getKey()).isEqualTo(testKey);
                  assertThat(element.getValue()).isInstanceOf(FakeStrategyState.class);

                  // Additional assertions on the state can be done here
                  FakeStrategyState state = (FakeStrategyState) element.getValue();
                  assertThat(state.updateRecordCalled).isTrue(); // Example assertion on the fake
                  return null;
                });

        pipeline.run().waitUntilFinish();

        verify(mockOrchestrator, times(1)).runOptimization(any(GAOptimizationRequest.class));
        GAOptimizationRequest actualRequest = gaRequestCaptor.getValue();
        assertThat(actualRequest.getCandlesList()).containsExactlyElementsIn(candles).inOrder();
        assertThat(actualRequest.getStrategyType())
            .isEqualTo(StrategyType.SMA_RSI); // Check strategy type
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
                                .withCoder(getKvCoder(StringUtf8Coder.of(), SerializableCoder.of((Class<ImmutableList<Candle>>) (Class<?>) ImmutableList.class))));


        BestStrategyResponse mockResponse1 = BestStrategyResponse.newBuilder().setBestScore(0.8).build();
        BestStrategyResponse mockResponse2 = BestStrategyResponse.newBuilder().setBestScore(0.9).build();

          when(mockOrchestrator.runOptimization(any(GAOptimizationRequest.class)))
                  .thenReturn(mockResponse1).thenReturn(mockResponse2);  //Return different responses for subsequent calls.

          // Act
        PCollection<KV<String, StrategyState>> output = input.apply(optimizeStrategies);

        // Assert (Using PAssert to verify the output)
          PAssert.that(output)
              .satisfies(
                  iterable -> {
                      KV<String, StrategyState> element = iterable.iterator().next();
                      assertThat(element.getKey()).isEqualTo(testKey);
                      assertThat(element.getValue()).isInstanceOf(FakeStrategyState.class);

                      FakeStrategyState state = (FakeStrategyState) element.getValue();
                      assertThat(state.updateRecordCalled).isTrue();
                      // Add assertions to check state for both strategy types if needed
                      return null;
                  });

        pipeline.run().waitUntilFinish();

        verify(mockOrchestrator, org.mockito.Mockito.times(2)).runOptimization(any(GAOptimizationRequest.class));  // Verify called twice.
    }

    // Fake implementation of StrategyState.Factory
    public static class FakeStrategyStateFactory implements StrategyState.Factory, Serializable {
        @Override
        public StrategyState create() {
            return new FakeStrategyState();
        }
    }

    // Fake implementation of StrategyState
    public static class FakeStrategyState implements StrategyState, Serializable {
        private StrategyType currentStrategyType = StrategyType.SMA_RSI;
        private final Map<StrategyType, StrategyRecord> strategyRecords = new ConcurrentHashMap<>();
        private boolean updateRecordCalled = false;

        @Override
        public org.ta4j.core.Strategy getCurrentStrategy(BarSeries series) {
            // Return a simple strategy, no need to mock
            return new BaseStrategy(new BooleanRule(true), new BooleanRule(false));
        }

        @Override
        public void updateRecord(StrategyType type, Any parameters, double score) {
            strategyRecords.put(type, new StrategyRecord(type, parameters, score));
            updateRecordCalled = true;
        }

        @Override
        public StrategyState selectBestStrategy(BarSeries series) {
            // Simplified selection logic for testing
            this.currentStrategyType = StrategyType.SMA_RSI; // Example
            return this;
        }

        @Override
        public com.verlumen.tradestream.strategies.Strategy toStrategyMessage() {
            // Create and return a Strategy message
            return com.verlumen.tradestream.strategies.Strategy.newBuilder().setType(currentStrategyType).build();
        }

        @Override
        public Iterable<StrategyType> getStrategyTypes() {
            return ImmutableList.of(StrategyType.SMA_RSI, StrategyType.EMA_MACD); // All available types
        }

        @Override
        public StrategyType getCurrentStrategyType() {
            return currentStrategyType;
        }

    }
}
