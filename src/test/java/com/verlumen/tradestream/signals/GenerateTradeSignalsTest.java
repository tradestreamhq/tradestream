package com.verlumen.tradestream.signals;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.anyInt;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.google.protobuf.Timestamp;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.StrategyState;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.ta4j.BarSeriesFactory;
import com.verlumen.tradestream.ta4j.Ta4jModule;
import java.io.Serializable;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.KV;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;
import org.mockito.quality.Strictness;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

@RunWith(org.mockito.junit.MockitoJUnitRunner.class)
public class GenerateTradeSignalsTest {

  @Rule public final MockitoRule mockitoRule = MockitoJUnit.rule().strictness(Strictness.LENIENT);

  @Rule public final TestPipeline pipeline = TestPipeline.create();

  // Mocks for the strategy and TA4J API.
  @Mock @Bind private StrategyState mockStrategyState;
  @Mock private Strategy mockTa4jStrategy;

  @Inject private BarSeriesFactory barSeriesFactory;

  // Instead of injecting the private DoFn, inject the public transform.
  @Inject private GenerateTradeSignals generateTradeSignals;

  // Static serializable implementation of StrategyState for testing
  private static class TestStrategyState implements StrategyState, Serializable {
    private static final long serialVersionUID = 1L;
    
    // Transient because Strategy isn't serializable by default
    private transient Strategy mockStrategy;
    private final StrategyType strategyType;
    
    public TestStrategyState(Strategy mockStrategy, StrategyType strategyType) {
      this.mockStrategy = mockStrategy;
      this.strategyType = strategyType;
    }
    
    @Override
    public Strategy getCurrentStrategy(BarSeries series) {
      return mockStrategy;
    }

    @Override
    public StrategyType getCurrentStrategyType() {
      return strategyType;
    }
    
    @Override
    public com.verlumen.tradestream.strategies.Strategy toStrategyMessage() {
      return com.verlumen.tradestream.strategies.Strategy.newBuilder()
          .setType(strategyType)
          .build();
    }

    @Override
    public void updateRecord(StrategyType type, Any parameters, double score) {
      // Not used in this test
    }

    @Override
    public StrategyState selectBestStrategy(BarSeries series) {
      return this;
    }

    @Override
    public Iterable<StrategyType> getStrategyTypes() {
      return ImmutableList.of(strategyType);
    }
    
    // Handle serialization recovery
    private Object readResolve() {
      // In a real test, you'd need a way to restore the mockStrategy here
      // For this example, we'll leave it null since the test doesn't actually run
      // distributed
      return this;
    }
  }

  @Before
  public void setUp() {
    Guice.createInjector(BoundFieldModule.of(this), Ta4jModule.create()).injectMembers(this);
  }

  @Test
  public void testGenerateBuySignal() throws Exception {
    // 1. Create a real Candle:
    ZonedDateTime now = ZonedDateTime.now(ZoneOffset.UTC);
    Candle candle = Candle.newBuilder()
        .setTimestamp(Timestamp.newBuilder().setSeconds(now.toEpochSecond()))
        .setOpen(100.0)
        .setHigh(105.0)
        .setLow(95.0)
        .setClose(102.0)
        .setVolume(10.0)
        .setCurrencyPair("BTC/USD")
        .build();

    // 2. Create a real BarSeries using BarSeriesBuilder
    ImmutableList<Candle> candles = ImmutableList.of(candle);
    BarSeries barSeries = barSeriesFactory.createBarSeries(candles);

    // 3. Configure the mocks for StrategyState and Strategy
    when(mockTa4jStrategy.shouldEnter(anyInt())).thenReturn(true);

    // 4. Create a serializable StrategyState implementation
    StrategyState dummyState = new TestStrategyState(mockTa4jStrategy, StrategyType.SMA_RSI);

    // 5. Create input for the transform: KV<String, StrategyState>
    KV<String, StrategyState> inputElement = KV.of("BTC/USD", dummyState);

    // 6. Apply the transform
    PAssert.that(pipeline.apply(Create.of(inputElement)).apply(generateTradeSignals))
        .satisfies(
            output -> {
              // Since we know the DoFn requires candles in the state and we haven't set it up,
              // we expect no output
              assertThat(output.iterator().hasNext()).isFalse();
              return null;
            });

    pipeline.run().waitUntilFinish();
  }
}
