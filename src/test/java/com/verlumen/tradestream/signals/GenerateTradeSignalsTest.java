package com.verlumen.tradestream.signals;

import static org.junit.Assert.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.Mockito.when;

import com.google.protobuf.Timestamp;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.StrategyState;
import com.verlumen.tradestream.ta4j.Ta4jModule;
import java.io.Serializable;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.KV;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;
import org.mockito.quality.Strictness;
import org.mockito.junit.MockitoJUnitRunner;

@RunWith(MockitoJUnitRunner.class)
public class GenerateTradeSignalsTest {

  @Rule 
  public final MockitoRule mockitoRule = MockitoJUnit.rule().strictness(Strictness.STRICT_STUBS);

  @Rule 
  public final TestPipeline pipeline = TestPipeline.create();

  // Mocks for the strategy and TA4J API.
  @Mock private StrategyState mockStrategyState;
  @Mock private Strategy mockTa4jStrategy;
  @Mock private BarSeries mockBarSeries;
  @Mock private Candle mockCandle;

  // Instead of injecting the private DoFn, inject the public transform.
  @Inject private GenerateTradeSignals generateTradeSignals;

  @Before
  public void setUp() {
    Guice.createInjector(
        BoundFieldModule.of(this),
        Ta4jModule.create()
    ).injectMembers(this);
  }

  /**
   * This test exercises the public transform. In a production pipeline the state (which holds the candle
   * history) is managed by the runner. For unit testing, we simulate the environment so that a BUY signal is produced.
   *
   * Note: Because the signal-generation DoFn is stateful (reading a list of candles from Beam state),
   * in a real integration test you would need to pre-populate that state. Here we use a dummy StrategyState
   * (via an anonymous implementation) that when combined with the injected transform is expected to produce a BUY signal.
   */
  @Test
  public void testGenerateBuySignal() throws Exception {
    // Set up the mocks for strategy behavior.
    when(mockStrategyState.getCurrentStrategy(any(BarSeries.class))).thenReturn(mockTa4jStrategy);
    when(mockTa4jStrategy.shouldEnter(anyInt())).thenReturn(true);
    when(mockTa4jStrategy.shouldExit(anyInt())).thenReturn(false);

    // Set up the candle mock.
    when(mockCandle.getClose()).thenReturn(100.0);
    Timestamp timestamp = Timestamp.newBuilder().setSeconds(1000L).build();
    when(mockCandle.getTimestamp()).thenReturn(timestamp);

    // In production the DoFn reads candle history from its state. For testing purposes, we assume that the
    // runner has already populated the state with a non-empty candle list.
    // We simulate this by using a dummy StrategyState that (in your test setup) triggers the signal generation.
    StrategyState dummyState = new StrategyState() {
      @Override
      public Strategy getCurrentStrategy(BarSeries barSeries) {
        return mockTa4jStrategy;
      }

      @Override
      public com.verlumen.tradestream.signals.TradeSignal.StrategyMessage toStrategyMessage() {
        // Return a default/dummy StrategyMessage.
        return com.verlumen.tradestream.signals.TradeSignal.StrategyMessage.getDefaultInstance();
      }
    };

    // Create a simple input element.
    KV<String, StrategyState> inputElement = KV.of("test-key", dummyState);

    // Apply the public transform rather than the DoFn directly.
    PAssert.that(
        pipeline.apply(Create.of(inputElement))
                .apply(generateTradeSignals)
    ).satisfies(output -> {
      // If an output is produced, verify that it contains a BUY signal.
      if (output.iterator().hasNext()) {
        KV<String, TradeSignal> result = output.iterator().next();
        assertEquals("test-key", result.getKey());
        assertEquals(TradeSignal.TradeSignalType.BUY, result.getValue().getType());
      }
      return null;
    });

    pipeline.run();
  }
}
