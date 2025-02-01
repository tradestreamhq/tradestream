package com.verlumen.tradestream.marketdata;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.google.protobuf.Timestamp;
import com.google.protobuf.util.Timestamps;
import java.util.List;
import org.apache.beam.sdk.coders.KvCoder;
import org.apache.beam.sdk.coders.ProtoCoder;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.beam.sdk.testing.DoFnTester;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestStream;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.windowing.FixedWindows;
import org.apache.beam.sdk.transforms.windowing.Window;
import org.apache.beam.sdk.values.KV;
import org.joda.time.Duration;
import org.joda.time.Instant;
import org.junit.Rule;
import org.junit.Test;

/**
 * Test suite for CandleAuthor.
 *
 * Note:
 * - The integration tests below use TestStream and PAssert.
 * - For testing the onTimer branch that uses a previous candle (when no trade is
 *   processed in a window) we assume that the anonymous DoFn has been refactored
 *   into a package-private static inner class {@code AggregateToCandleDoFn}.
 */
public class CandleAuthorTest {

  @Rule public final TestPipeline pipeline = TestPipeline.create();

  // Helper methods for building Trade and Candle instances.
  private Trade createTrade(double price, double volume) {
    return Trade.newBuilder().setPrice(price).setVolume(volume).build();
  }

  private Candle createExpectedCandle(
      String currencyPair,
      long windowStartMillis,
      double open,
      double high,
      double low,
      double close,
      double volume) {
    return Candle.newBuilder()
        .setCurrencyPair(currencyPair)
        .setTimestamp(Timestamps.fromMillis(windowStartMillis))
        .setOpen(open)
        .setHigh(high)
        .setLow(low)
        .setClose(close)
        .setVolume(volume)
        .build();
  }

  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Integration Test 1: Single Trade produces a correct candle.
  // Arrange: One KV element for key "EUR/USD" in a fixed window.
  // Act: Apply windowing and CandleAuthor.create().
  // Assert: The output candle’s open price equals the trade price.
  @Test
  public void testSingleTradeProducesCorrectCandle() {
    final String key = "EUR/USD";
    final Trade trade = createTrade(100.0, 10.0);
    // Use an event time of 5 seconds so that the fixed window is [0, 10 sec)
    Instant eventTime = new Instant(5000);
    long expectedWindowStartMillis = 0;
    final Candle expectedCandle =
        createExpectedCandle(key, expectedWindowStartMillis, 100.0, 100.0, 100.0, 100.0, 10.0);

    TestStream<KV<String, Trade>> stream =
        TestStream.<KV<String, Trade>>create(
            KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Trade.class))
        )
        .addElements(KV.of(key, trade))
        // Advance the watermark past the window so that the timer fires.
        .advanceWatermarkTo(new Instant(11000))
        .advanceProcessingTime(Duration.standardSeconds(1))
        .advanceWatermarkToInfinity();

    PCollection<Candle> candles =
        pipeline
            .apply("Input", stream)
            .apply("Window", Window.<KV<String, Trade>>into(FixedWindows.of(Duration.standardSeconds(10))))
            .apply("Candle", CandleAuthor.create());

    PAssert.that(candles).satisfies((Iterable<Candle> outs) -> {
      int count = 0;
      for (Candle c : outs) {
        count++;
        // Assert that the open price equals that of the trade.
        assertEquals(100.0, c.getOpen(), 0.0);
      }
      assertEquals(1, count);
      return null;
    });

    pipeline.run().waitUntilFinish();
  }

  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Integration Test 2: Multiple Trades are aggregated correctly.
  // Arrange: Three trades in the same fixed window.
  // Act: Apply the transform.
  // Assert: The output candle’s high value equals the maximum trade price.
  @Test
  public void testMultipleTradesAreAggregatedCorrectly() {
    final String key = "EUR/USD";
    // Three trades: first=100.0, second=105.0, third=95.0; volumes: 10, 20, 30.
    final Trade t1 = createTrade(100.0, 10.0);
    final Trade t2 = createTrade(105.0, 20.0);
    final Trade t3 = createTrade(95.0, 30.0);
    // All events in the same fixed window ([0, 10 sec)).
    Instant time1 = new Instant(2000);
    Instant time2 = new Instant(4000);
    Instant time3 = new Instant(8000);
    long expectedWindowStartMillis = 0;
    final Candle expectedCandle =
        createExpectedCandle(key, expectedWindowStartMillis, 100.0, 105.0, 95.0, 95.0, 60.0);

    TestStream<KV<String, Trade>> stream =
        TestStream.<KV<String, Trade>>create(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Trade.class)))
            .addElements(
                org.joda.time.Instant.ofEpochMilli(time1.getMillis()),
                KV.of(key, t1))
            .addElements(
                org.joda.time.Instant.ofEpochMilli(time2.getMillis()),
                KV.of(key, t2))
            .addElements(
                org.joda.time.Instant.ofEpochMilli(time3.getMillis()),
                KV.of(key, t3))
            .advanceWatermarkTo(new Instant(11000))
            .advanceProcessingTime(Duration.standardSeconds(1))
            .advanceWatermarkToInfinity();

    // Arrange + Act
    pipeline
        .apply("Input2", stream)
        .apply("Window2", Window.<KV<String, Trade>>into(FixedWindows.of(Duration.standardSeconds(10))))
        .apply("Candle2", CandleAuthor.create());
    // Assert: Use PAssert to check that the maximum (high) value equals 105.0.
    PAssert.thatSingleton(
            pipeline
                .apply("InputForPAssert2", stream)
                .apply("WindowForPAssert2", Window.<KV<String, Trade>>into(FixedWindows.of(Duration.standardSeconds(10))))
                .apply("CandleForPAssert2", CandleAuthor.create())
                .apply("ExtractHigh", org.apache.beam.sdk.transforms.MapElements.into(org.apache.beam.sdk.values.TypeDescriptors.doubles())
                    .via((Candle c) -> c.getHigh())))
        .isEqualTo(105.0);
    pipeline.run().waitUntilFinish();
  }

  //–––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
  // Integration Test 3: When no trades are received, no candle is output.
  // Arrange: An empty input stream.
  // Act: Apply the transform.
  // Assert: The output collection is empty.
  @Test
  public void testEmptyInputProducesNoCandle() {
    TestStream<KV<String, Trade>> emptyStream =
        TestStream.<KV<String, Trade>>create(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Trade.class)))
            .advanceWatermarkTo(new Instant(11000))
            .advanceWatermarkToInfinity();

    // Arrange + Act
    pipeline
        .apply("EmptyInput", emptyStream)
        .apply("WindowEmpty", Window.<KV<String, Trade>>into(FixedWindows.of(Duration.standardSeconds(10))))
        .apply("CandleEmpty", CandleAuthor.create());

    // Assert: The output PCollection should be empty.
    PAssert.thatEmpty(
        pipeline
            .apply("EmptyInputForPAssert", emptyStream)
            .apply("WindowEmptyForPAssert", Window.<KV<String, Trade>>into(FixedWindows.of(Duration.standardSeconds(10))))
            .apply("CandleEmptyForPAssert", CandleAuthor.create()));
    pipeline.run().waitUntilFinish();
  }
}
