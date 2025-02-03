package com.verlumen.tradestream.transforms;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.fail; 
 
import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableList;
import java.util.List;
import org.apache.beam.sdk.transforms.DoFn.ProcessElement;
import org.apache.beam.sdk.transforms.DoFnTester;
import org.apache.beam.sdk.transforms.DoFnTester;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.KV;
import org.apache.commons.collections4.queue.CircularFifoQueue;
import org.junit.Before;
import org.junit.Test;

public class GetLastNElementsDoFnTest {

    // --- Test 1: Single element ---
    @Test
    public void testSingleElementOutput() throws Exception {
        // Arrange: Create a DoFn tester with capacity 3
        DoFnTester<KV<Integer, String>, KV<Integer, ImmutableList<String>>> fnTester =
            DoFnTester.of(GetLastNElementsDoFn.<Integer, String>create(3));

        // Act: Process a single element
        fnTester.processElement(KV.of(1, "a"));
        List<KV<Integer, ImmutableList<String>>> outputs = fnTester.takeOutputElements();

        // Assert: The output for key 1 should be exactly ["a"]
        assertEquals("Expected one-element output",
            KV.of(1, ImmutableList.of("a")), 
            outputs.get(0));
    }

    // --- Test 2: Two elements within capacity ---
    @Test
    public void testTwoElementsOutput() throws Exception {
        // Arrange: Create a DoFn tester with capacity 3
        DoFnTester<KV<Integer, String>, KV<Integer, ImmutableList<String>>> fnTester =
            DoFnTester.of(GetLastNElementsDoFn.<Integer, String>create(3));

        // Act: Process the first element and then a second element
        fnTester.processElement(KV.of(1, "a"));
        fnTester.processElement(KV.of(1, "b"));
        List<KV<Integer, ImmutableList<String>>> outputs = fnTester.takeOutputElements();

        // Assert: The last output should be ["a", "b"]
        assertEquals("Expected two-element output in order",
            KV.of(1, ImmutableList.of("a", "b")),
            outputs.get(1));
    }

    // --- Test 3: Buffer eviction when capacity is exceeded ---
    @Test
    public void testEvictionWhenExceedCapacity() throws Exception {
        // Arrange: Create a DoFn tester with capacity 3
        DoFnTester<KV<Integer, String>, KV<Integer, ImmutableList<String>>> fnTester =
            DoFnTester.of(GetLastNElementsDoFn.<Integer, String>create(3));

        // Act: Process 4 elements in sequence
        fnTester.processElement(KV.of(1, "a")); // Buffer: [a]
        fnTester.processElement(KV.of(1, "b")); // Buffer: [a, b]
        fnTester.processElement(KV.of(1, "c")); // Buffer: [a, b, c]
        fnTester.processElement(KV.of(1, "d")); // Buffer becomes [b, c, d]
        List<KV<Integer, ImmutableList<String>>> outputs = fnTester.takeOutputElements();

        // Assert: The last output should contain the last three elements
        assertEquals("Expected eviction of the oldest element, resulting in [b, c, d]",
            KV.of(1, ImmutableList.of("b", "c", "d")),
            outputs.get(3));
    }

    // --- Test 4: Multiple keys state isolation ---
    @Test
    public void testMultipleKeysStateIsolation() throws Exception {
        // Arrange: Create a DoFn tester with capacity 3
        DoFnTester<KV<Integer, String>, KV<Integer, ImmutableList<String>>> fnTester =
            DoFnTester.of(GetLastNElementsDoFn.<Integer, String>create(3));

        // Act: Process elements for two different keys
        fnTester.processElement(KV.of(1, "a"));
        fnTester.processElement(KV.of(2, "x"));
        List<KV<Integer, ImmutableList<String>>> outputs = fnTester.takeOutputElements();

        // Assert: Each key should have its own state
        assertEquals("Expected key 1 to have state [a]",
            KV.of(1, ImmutableList.of("a")),
            outputs.get(0));

        assertEquals("Expected key 2 to have state [x]",
            KV.of(2, ImmutableList.of("x")),
            outputs.get(1));
    }

    // --- Test 5: Null value should throw an exception ---
    @Test
    public void testNullValueThrowsException() throws Exception {
        // Arrange: Create a DoFn tester with capacity 3
        DoFnTester<KV<Integer, String>, KV<Integer, ImmutableList<String>>> fnTester =
            DoFnTester.of(GetLastNElementsDoFn.<Integer, String>create(3));

        // Act & Assert: Processing a null value should throw a NullPointerException
        try {
            fnTester.processElement(KV.of(1, null));
            fail("Expected a NullPointerException when processing a null value");
        } catch (NullPointerException expected) {
            // Test passes - expected exception was thrown
        }
    }

    // --- Test 6: Zero capacity should throw an exception ---
    @Test
    public void testZeroCapacityThrowsException() throws Exception {
        // Arrange: Create a DoFn with capacity zero
        DoFnTester<KV<Integer, String>, KV<Integer, ImmutableList<String>>> fnTester =
            DoFnTester.of(GetLastNElementsDoFn.<Integer, String>create(0));

        // Act & Assert: Processing an element should throw an IllegalArgumentException
        try {
            fnTester.processElement(KV.of(1, "a"));
            fail("Expected an IllegalArgumentException due to zero capacity");
        } catch (IllegalArgumentException expected) {
            // Test passes - expected exception was thrown
        }
    }
}
