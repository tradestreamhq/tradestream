package com.verlumen.tradestream.transforms;


import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.CoreMatchers.contains;
import static org.hamcrest.Matchers.containsInRelativeOrder;
import static org.hamcrest.CoreMatchers.empty;
import static org.junit.Assert.fail;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import java.util.List;
import org.apache.beam.sdk.transforms.DoFn.ProcessElement;
import org.apache.beam.sdk.transforms.DoFnTester;
import org.apache.beam.sdk.values.KV;
import org.apache.commons.collections4.queue.CircularFifoQueue;
import org.junit.Before;
import org.junit.Test;

public class GetLastNElementsDoFnTest {

  // --- Test 1: Single element ---
  @Test
  public void testSingleElementOutput() throws Exception {
    // Arrange: Create a DoFn tester with capacity 3.
    DoFnTester<KV<Integer, String>, KV<Integer, ImmutableList<String>>> fnTester =
        DoFnTester.of(GetLastNElementsDoFn.<Integer, String>create(3));

    // Act: Process a single element.
    List<KV<Integer, ImmutableList<String>>> outputs = fnTester.processElement(KV.of(1, "a"));

    // Assert: The output for key 1 should be exactly ["a"].
    assertThat("Expected one-element output",
        outputs,
        contains(KV.of(1, ImmutableList.of("a"))));
  }

  // --- Test 2: Two elements within capacity ---
  @Test
  public void testTwoElementsOutput() throws Exception {
    // Arrange: Create a DoFn tester with capacity 3.
    DoFnTester<KV<Integer, String>, KV<Integer, ImmutableList<String>>> fnTester =
        DoFnTester.of(GetLastNElementsDoFn.<Integer, String>create(3));

    // Act: Process the first element and then a second element.
    fnTester.processElement(KV.of(1, "a"));
    List<KV<Integer, ImmutableList<String>>> outputs2 = fnTester.processElement(KV.of(1, "b"));

    // Assert: The output of the second call should be ["a", "b"].
    assertThat("Expected two-element output in order",
        outputs2,
        contains(KV.of(1, ImmutableList.of("a", "b"))));
  }

  // --- Test 3: Buffer eviction when capacity is exceeded ---
  @Test
  public void testEvictionWhenExceedCapacity() throws Exception {
    // Arrange: Create a DoFn tester with capacity 3.
    DoFnTester<KV<Integer, String>, KV<Integer, ImmutableList<String>>> fnTester =
        DoFnTester.of(GetLastNElementsDoFn.<Integer, String>create(3));

    // Act: Process 4 elements in sequence.
    fnTester.processElement(KV.of(1, "a")); // Buffer: [a]
    fnTester.processElement(KV.of(1, "b")); // Buffer: [a, b]
    fnTester.processElement(KV.of(1, "c")); // Buffer: [a, b, c]
    List<KV<Integer, ImmutableList<String>>> outputs4 = fnTester.processElement(KV.of(1, "d")); // Buffer becomes [b, c, d]

    // Assert: The output of the fourth call should contain the last three elements.
    assertThat("Expected eviction of the oldest element, resulting in [b, c, d]",
        outputs4,
        contains(KV.of(1, ImmutableList.of("b", "c", "d"))));
  }

  // --- Test 4: Multiple keys state isolation ---
  @Test
  public void testMultipleKeysStateIsolation() throws Exception {
    // Arrange: Create a DoFn tester with capacity 3.
    DoFnTester<KV<Integer, String>, KV<Integer, ImmutableList<String>>> fnTester =
        DoFnTester.of(GetLastNElementsDoFn.<Integer, String>create(3));

    // Act: Process elements for two different keys.
    List<KV<Integer, ImmutableList<String>>> outputKey1 = fnTester.processElement(KV.of(1, "a"));
    List<KV<Integer, ImmutableList<String>>> outputKey2 = fnTester.processElement(KV.of(2, "x"));

    // Assert: Each key should have its own state; key 1 should output ["a"].
    assertThat("Expected key 1 to have state [a]",
        outputKey1,
        contains(KV.of(1, ImmutableList.of("a"))));

    // Note: We use separate test assertions per test case. In a real
    // granular test suite, you might separate these into two tests.
    // Here, for brevity, we have two assertions in one test,
    // but each one checks a distinct key’s state.
    assertThat("Expected key 2 to have state [x]",
        outputKey2,
        contains(KV.of(2, ImmutableList.of("x"))));
  }

  // --- Test 5: Null value should throw an exception ---
  @Test
  public void testNullValueThrowsException() throws Exception {
    // Arrange: Create a DoFn tester with capacity 3.
    DoFnTester<KV<Integer, String>, KV<Integer, ImmutableList<String>>> fnTester =
        DoFnTester.of(GetLastNElementsDoFn.<Integer, String>create(3));

    // Act & Assert: Processing a null value should throw a NullPointerException.
    try {
      fnTester.processElement(KV.of(1, null));
      fail("Expected a NullPointerException when processing a null value");
    } catch (NullPointerException expected) {
      // One assertion: exception thrown.
    }
  }

  // --- Test 6: Zero capacity should throw an exception when processing ---
  @Test
  public void testZeroCapacityThrowsException() throws Exception {
    // Arrange: Create a DoFn with capacity zero.
    // Note: CircularFifoQueue does not support a capacity of zero.
    DoFnTester<KV<Integer, String>, KV<Integer, ImmutableList<String>>> fnTester =
        DoFnTester.of(GetLastNElementsDoFn.<Integer, String>create(0));

    // Act & Assert: Processing an element should throw an IllegalArgumentException.
    try {
      fnTester.processElement(KV.of(1, "a"));
      fail("Expected an IllegalArgumentException due to zero capacity");
    } catch (IllegalArgumentException expected) {
      // One assertion: exception thrown.
    }
  }
}
