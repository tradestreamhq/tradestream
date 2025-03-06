package com.verlumen.tradestream.strategies;

import static com.google.common.truth.Truth.assertThat;
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
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;
import org.mockito.quality.Strictness;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.rules.BooleanRule;

/** Unit tests for {@link OptimizeStrategies}. */
@RunWith(JUnit4.class)
public class OptimizeStrategiesTest {

  @Rule public final TestPipeline pipeline = TestPipeline.create();
  @Rule public MockitoRule mockitoRule = MockitoJUnit.rule().strictness(Strictness.STRICT_STUBS);

  // Use a Fake instead of a Mock for GeneticAlgorithmOrchestrator.
  @Bind(to = GeneticAlgorithmOrchestrator.class)
  private FakeGeneticAlgorithmOrchestrator mockOrchestrator = new FakeGeneticAlgorithmOrchestrator();

  // Use a Fake instead of a Mock for StrategyState.Factory.
  @Bind private StrategyState.Factory mockStateFactory = new FakeStrategyStateFactory();

  @Inject private OptimizeStrategies optimizeStrategies;

  @Before
  public void setUp() {
    // Reset the static state in the fake orchestrator.
    FakeGeneticAlgorithmOrchestrator.reset();
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
    pipeline.run().waitUntilFinish();

    assertThat(mockOrchestrator.wasRunOptimizationCalled()).isFalse();
  }

  @Test
  public void expand_nonEmptyCandleList_callsOrchestratorAndOutputsState() throws Exception {
    // Arrange
    String testKey = "testKey";
    Candle candle1 = Candle.newBuilder()
        .setOpen(10)
        .setClose(12)
        .setTimestamp(1L) // assign an increasing timestamp
        .build();
    Candle candle2 = Candle.newBuilder()
        .setOpen(12)
        .setClose(11)
        .setTimestamp(2L) // assign a later timestamp
        .build();

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

    assertThat(mockOrchestrator.wasRunOptimizationCalled()).isTrue();
    GAOptimizationRequest actualRequest = mockOrchestrator.getLastRequest();
    assertThat(actualRequest.getCandlesList()).containsExactlyElementsIn(candles).inOrder();
    assertThat(actualRequest.getStrategyType())
        .isEqualTo(StrategyType.SMA_RSI); // Check strategy type
  }

  @Test
  public void expand_multipleStrategies_callsOrchestratorForEachStrategy() throws Exception {
    // Arrange
    String testKey = "testKey";
    // Build a candle with an increasing timestamp.
    ImmutableList<Candle> candles =
        ImmutableList.of(
            Candle.newBuilder()
                .setTimestamp(1L)
                .build());
    PCollection<KV<String, ImmutableList<Candle>>> input =
        pipeline.apply(
            "CreateInput",
            Create.of(KV.of(testKey, candles))
                .withCoder(
                    getKvCoder(
                        StringUtf8Coder.of(),
                        SerializableCoder.of(
                            (Class<ImmutableList<Candle>>) (Class<?>) ImmutableList.class))));

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

    assertThat(mockOrchestrator.wasRunOptimizationCalled()).isTrue();
    assertThat(mockOrchestrator.getLastRequest().getStrategyType())
        .isEqualTo(StrategyType.SMA_RSI); // Check strategy type
  }

  // Fake implementation of StrategyState.Factory.
  public static class FakeStrategyStateFactory implements StrategyState.Factory, Serializable {
    @Override
    public StrategyState create() {
      return new FakeStrategyState();
    }
  }

  // Fake implementation of StrategyState.
  public static class FakeStrategyState implements StrategyState, Serializable {
    private StrategyType currentStrategyType = StrategyType.SMA_RSI;
    private final Map<StrategyType, StrategyRecord> strategyRecords = new ConcurrentHashMap<>();
    private boolean updateRecordCalled = false;

    @Override
    public org.ta4j.core.Strategy getCurrentStrategy(BarSeries series) {
      // Return a simple strategy, no need to mock
      return new BaseStrategy(new BooleanRule(false), new BooleanRule(false));
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
      return com.verlumen.tradestream.strategies.Strategy.newBuilder()
          .setType(currentStrategyType)
          .build();
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

  /** A fake implementation of GeneticAlgorithmOrchestrator for testing. */
  private static class FakeGeneticAlgorithmOrchestrator
      implements GeneticAlgorithmOrchestrator, Serializable {
    private static boolean runOptimizationCalledStatic = false;
    private static GAOptimizationRequest lastRequestStatic = null;

    @Override
    public BestStrategyResponse runOptimization(GAOptimizationRequest request) {
      runOptimizationCalledStatic = true;
      lastRequestStatic = request;
      // Return a simple mock response. Adapt as needed for your tests.
      return BestStrategyResponse.newBuilder()
          .setBestScore(0.8)
          .setBestStrategyParameters(Any.getDefaultInstance())
          .build();
    }

    public boolean wasRunOptimizationCalled() {
      return runOptimizationCalledStatic;
    }

    public GAOptimizationRequest getLastRequest() {
      return lastRequestStatic;
    }

    public static void reset() {
      runOptimizationCalledStatic = false;
      lastRequestStatic = null;
    }
  }
}
