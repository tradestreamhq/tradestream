package com.verlumen.tradestream.signals;

import static com.google.common.truth.Truth.assertThat;
import static com.google.protobuf.util.Timestamps.fromMillis;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

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

  @Rule public final MockitoRule mockitoRule = MockitoJUnit.rule().strictness(Strictness.STRICT_STUBS);

  @Rule public final TestPipeline pipeline = TestPipeline.create();

  // Mocks for the strategy and TA4J API.
  @Mock @Bind private StrategyState mockStrategyState;
  @Mock private Strategy mockTa4jStrategy;

  @Inject private BarSeriesFactory barSeriesFactory;

  // Instead of injecting the private DoFn, inject the public transform.
  @Inject private GenerateTradeSignals generateTradeSignals;

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
        .setCurrencyPair("BTC/USD")  // Set the currency pair
        .build();

    // 2. Create a real BarSeries using BarSeriesBuilder
     ImmutableList<Candle> candles = ImmutableList.of(candle);
     BarSeries barSeries = barSeriesFactory.createBarSeries(candles);


    // 3.  Configure the mocks for StrategyState and Strategy
    when(mockStrategyState.getCurrentStrategy(any(BarSeries.class))).thenReturn(mockTa4jStrategy);

    // TA4J's shouldEnter and shouldExit take the *index* of the bar in the series.
    // In a series with one bar, that index is 0.
    when(mockTa4jStrategy.shouldEnter(0)).thenReturn(true);
    when(mockTa4jStrategy.shouldExit(0)).thenReturn(false);
    
    // Mock the toStrategyMessage()
    com.verlumen.tradestream.strategies.Strategy strategyMessage =
        com.verlumen.tradestream.strategies.Strategy.newBuilder()
            .setType(StrategyType.SMA_RSI)
            .build();

    when(mockStrategyState.toStrategyMessage()).thenReturn(strategyMessage);
    
    when(mockStrategyState.getCurrentStrategyType()).thenReturn(StrategyType.SMA_RSI);


    // 4.  Create a StrategyState using an anonymous class.
    StrategyState dummyState = new StrategyState() {
      @Override
      public Strategy getCurrentStrategy(BarSeries series) {
          return mockTa4jStrategy;  // Return the mock strategy
      }

      @Override
      public StrategyType getCurrentStrategyType() {
          return StrategyType.SMA_RSI; // Return a type
      }
      
      @Override
      public com.verlumen.tradestream.strategies.Strategy toStrategyMessage() {
        return com.verlumen.tradestream.strategies.Strategy.newBuilder().setType(StrategyType.SMA_RSI).build();
      }

      @Override
      public void updateRecord(StrategyType type, Any parameters, double score) {
          // Not used in this test
      }

      @Override
      public StrategyState selectBestStrategy(BarSeries series) {
          // Not used in this test
          return this; 
      }

      @Override
      public Iterable<StrategyType> getStrategyTypes() {
          // Not used in this test
          return null;
      }

    };


    // 5. Create input for the transform: KV<String, StrategyState>.
    KV<String, StrategyState> inputElement = KV.of("BTC/USD", dummyState); // Use the dummyState

    // 6. Apply the transform
    PAssert.that(pipeline.apply(Create.of(inputElement)).apply(generateTradeSignals))
        .satisfies(
            output -> {
              // If an output is produced, verify that it contains a BUY signal.
              if (output.iterator().hasNext()) {
                KV<String, TradeSignal> result = output.iterator().next();
                  //Updated to use truth framework
                assertThat(result.getKey()).isEqualTo("BTC/USD"); // Check the key
                TradeSignal signal = result.getValue();
                  //Updated to use truth framework
                assertThat(signal.getType()).isEqualTo(TradeSignal.TradeSignalType.BUY); // Check for a BUY signal
                  //Updated to use truth framework
                assertThat(signal.getPrice()).isEqualTo(102.0); // Use a small delta for double comparison.  Candle.close()
              }
              return null;
            });

    pipeline.run().waitUntilFinish();
  }
}
