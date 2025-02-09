package com.verlumen.tradestream.marketdata;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.time.TimeFrame;
import java.util.Arrays;
import org.apache.beam.sdk.coders.KvCoder;
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.KV;
import org.joda.time.Duration;
import org.junit.Rule;
import org.junit.Test;

public class MultiTimeframeCandleTransformTest {

    @Rule 
    public final TestPipeline pipeline = TestPipeline.create();

    @Test
    public void testMultiTimeframeTransform() {
        // Arrange: Create a base candle stream.
        // For this test, we simulate a base candle stream by creating two Candle objects
        // with different timestamps for key "BTC/USD". These candles might come, for example,
        // from the output of CandleStreamWithDefaults.
        Candle baseCandle1 = Candle.newBuilder()
                .setOpen(10000.0)
                .setHigh(10100.0)
                .setLow(9900.0)
                .setClose(10050.0)
                .setVolume(1.5)
                .setTimestamp(com.google.protobuf.Timestamp.newBuilder().setSeconds(1000).build())
                .setCurrencyPair("BTC/USD")
                .build();

        Candle baseCandle2 = Candle.newBuilder()
                .setOpen(10050.0)
                .setHigh(10200.0)
                .setLow(10000.0)
                .setClose(10150.0)
                .setVolume(2.0)
                .setTimestamp(com.google.protobuf.Timestamp.newBuilder().setSeconds(2000).build())
                .setCurrencyPair("BTC/USD")
                .build();
        int expectedBranches = TimeFrame.values().length;

        // Create the base stream as a PCollection of KV pairs.
        // Note that the key is "BTC/USD" and the value is the base candle.
        // For simplicity, we simulate the stream by emitting two elements.
        PAssert.that(
            pipeline.apply(Create.of(
                KV.of("BTC/USD", baseCandle1),
                KV.of("BTC/USD", baseCandle2)
            )).setCoder(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle.class)))
            .apply(new MultiTimeframeCandleTransform())
        ).satisfies(iterable -> {
            int count = 0;
            for (KV<String, ImmutableList<Candle>> kv : iterable) {
                // For key "BTC/USD", we expect each branch to produce at least one buffered list.
                // Since we have five branches, the flattened output should have 5 elements.
                assertEquals("BTC/USD", kv.getKey());
                assertTrue("Expected non-empty buffered list", kv.getValue().size() >= 1);
                count++;
            }
            assertEquals(
                "Expected " +
                expectedBranches +
                " branches (timeframes) in the output", expectedBranches, count);
            return null;
        });

        pipeline.run().waitUntilFinish();
    }
}
