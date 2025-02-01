package com.verlumen.tradestream.marketdata;

import com.google.protobuf.Timestamp;
import com.google.protobuf.util.Timestamps;
import java.util.Arrays;
import java.util.List;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.PCollection;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

/**
 * Unit tests for {@link ParseTrades}. Each test follows the Arrange-Act-Assert (AAA)
 * pattern with one assertion per test case.
 */
@RunWith(JUnit4.class)
public class ParseTradesTest {

    // The TestPipeline rule creates a Beam pipeline for testing.
    @Rule
    public final TestPipeline pipeline = TestPipeline.create();

    /**
     * Test that a valid Trade message (encoded as a byte array) is correctly parsed.
     *
     * <p>Arrange: Build a valid Trade with all expected fields set.
     * <br>Act: Create a PCollection containing this byte array and apply ParseTrades.
     * <br>Assert: The output contains exactly the expected Trade message.
     */
    @Test
    public void testValidTradeParsing() throws Exception {
        // Arrange
        Trade expectedTrade = Trade.newBuilder()
            // Build a Timestamp (using an epoch value, for example)
            .setTimestamp(Timestamp.newBuilder().setSeconds(1620000000).setNanos(0).build())
            .setExchange("TestExchange")
            .setCurrencyPair("BTC/USD")
            .setPrice(10000.0)
            .setVolume(0.5)
            .setTradeId("trade123")
            .build();
        byte[] validTradeBytes = expectedTrade.toByteArray();

        // Act
        PCollection<byte[]> input = pipeline.apply("CreateValidTrade", Create.of(validTradeBytes));
        PCollection<Trade> output = input.apply(new ParseTrades());

        // Assert: Verify that the output PCollection contains exactly the expected Trade.
        PAssert.that(output).containsInAnyOrder(expectedTrade);

        // Run the pipeline.
        pipeline.run().waitUntilFinish();
    }

    /**
     * Test that an invalid byte array (which does not represent a valid Trade) produces no output.
     *
     * <p>Arrange: Create an invalid byte array.
     * <br>Act: Apply ParseTrades to a PCollection with the invalid byte array.
     * <br>Assert: The output PCollection is empty.
     */
    @Test
    public void testInvalidTradeParsing() throws Exception {
        // Arrange: An arbitrary byte array that does not represent a valid Trade.
        byte[] invalidBytes = new byte[]{0, 1, 2, 3};

        // Act
        PCollection<byte[]> input = pipeline.apply("CreateInvalidTrade", Create.of(invalidBytes));
        PCollection<Trade> output = input.apply(new ParseTrades());

        // Assert: The output should be empty because parsing fails.
        PAssert.that(output).empty();

        // Run the pipeline.
        pipeline.run().waitUntilFinish();
    }

    /**
     * Test that a mix of valid and invalid Trade byte arrays results in output containing only the
     * valid Trade message.
     *
     * <p>Arrange: Create one valid Trade byte array and one invalid byte array.
     * <br>Act: Apply ParseTrades.
     * <br>Assert: The output contains only the valid Trade.
     */
    @Test
    public void testMixedValidAndInvalidTradeParsing() throws Exception {
        // Arrange: Build a valid Trade message.
        Trade expectedTrade = Trade.newBuilder()
            .setTimestamp(Timestamp.newBuilder().setSeconds(1620001000).setNanos(0).build())
            .setExchange("TestExchange")
            .setCurrencyPair("BTC/USD")
            .setPrice(5000.0)
            .setVolume(1.0)
            .setTradeId("trade456")
            .build();
        byte[] validTradeBytes = expectedTrade.toByteArray();
        byte[] invalidBytes = new byte[]{9, 8, 7}; // An invalid byte array.

        // Act
        List<byte[]> inputs = Arrays.asList(validTradeBytes, invalidBytes);
        PCollection<byte[]> input = pipeline.apply("CreateMixedTrades", Create.of(inputs));
        PCollection<Trade> output = input.apply(new ParseTrades());

        // Assert: Only the valid Trade should be present in the output.
        PAssert.that(output).containsInAnyOrder(expectedTrade);

        // Run the pipeline.
        pipeline.run().waitUntilFinish();
    }

    /**
     * Test that an empty input PCollection produces an empty output.
     *
     * <p>Arrange: Create an empty PCollection.
     * <br>Act: Apply ParseTrades.
     * <br>Assert: The output is empty.
     */
    @Test
    public void testEmptyInput() throws Exception {
        // Arrange: Create an empty PCollection of byte[].
        PCollection<byte[]> input = pipeline.apply("CreateEmptyInput", Create.empty(byte[].class));

        // Act
        PCollection<Trade> output = input.apply(new ParseTrades());

        // Assert: The output should be empty.
        PAssert.that(output).empty();

        // Run the pipeline.
        pipeline.run().waitUntilFinish();
    }

    /**
     * Test that multiple valid Trade messages are all parsed correctly.
     *
     * <p>Arrange: Create multiple valid Trade messages and convert them to byte arrays.
     * <br>Act: Apply ParseTrades to a PCollection of these byte arrays.
     * <br>Assert: The output contains all the Trade messages.
     */
    @Test
    public void testMultipleValidTrades() throws Exception {
        // Arrange: Build two valid Trade messages.
        Trade trade1 = Trade.newBuilder()
            .setTimestamp(Timestamp.newBuilder().setSeconds(1620002000).setNanos(0).build())
            .setExchange("Exchange1")
            .setCurrencyPair("BTC/USD")
            .setPrice(9000.0)
            .setVolume(0.3)
            .setTradeId("trade001")
            .build();

        Trade trade2 = Trade.newBuilder()
            .setTimestamp(Timestamp.newBuilder().setSeconds(1620003000).setNanos(0).build())
            .setExchange("Exchange2")
            .setCurrencyPair("ETH/USD")
            .setPrice(200.0)
            .setVolume(5.0)
            .setTradeId("trade002")
            .build();

        byte[] trade1Bytes = trade1.toByteArray();
        byte[] trade2Bytes = trade2.toByteArray();

        // Act
        List<byte[]> tradesBytes = Arrays.asList(trade1Bytes, trade2Bytes);
        PCollection<byte[]> input = pipeline.apply("CreateMultipleValidTrades", Create.of(tradesBytes));
        PCollection<Trade> output = input.apply(new ParseTrades());

        // Assert: The output should contain both Trade messages.
        PAssert.that(output).containsInAnyOrder(trade1, trade2);

        // Run the pipeline.
        pipeline.run().waitUntilFinish();
    }
}
