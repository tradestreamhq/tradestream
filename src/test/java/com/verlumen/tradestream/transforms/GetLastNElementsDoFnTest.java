package com.verlumen.tradestream.transforms;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import java.util.List;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.transforms.windowing.FixedWindows;
import org.apache.beam.sdk.transforms.windowing.Window;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.joda.time.Duration;
import org.junit.Rule;
import org.junit.Test;

public class GetLastNElementsDoFnTest {
  // Declare the pipeline as a public JUnit rule.
  @Rule
  public final transient TestPipeline pipeline = TestPipeline.create();

  // --- Test 1: Single element ---
  @Test
  public void testSingleElementOutput() {
    // Create a keyed input in a fixed window (stateful DoFns require non-global windows)
    PCollection<KV<Integer, String>> input =
        pipeline
            .apply(Create.of(KV.of(1, "a")))
            .apply(Window.into(FixedWindows.of(Duration.standardMinutes(5))));

    // Apply the DoFn with capacity 3
    PCollection<KV<Integer, ImmutableList<String>>> output =
        input.apply(ParDo.of(GetLastNElementsDoFn.<Integer, String>create(3)));

    // Expect one output: after processing "a", the state is ["a"]
    PAssert.that(output).containsInAnyOrder(KV.of(1, ImmutableList.of("a")));

    pipeline.run().waitUntilFinish();
  }

  // --- Test 2: Two elements within capacity ---
  @Test
  public void testTwoElementsOutput() {
    PCollection<KV<Integer, String>> input =
        pipeline
            .apply(Create.of(KV.of(1, "a"), KV.of(1, "b")))
            .apply(Window.into(FixedWindows.of(Duration.standardMinutes(5))));

    PCollection<KV<Integer, ImmutableList<String>>> output =
        input.apply(ParDo.of(GetLastNElementsDoFn.<Integer, String>create(3)));

    // Two outputs are expected:
    //  - After "a": state is ["a"]
    //  - After "b": state is ["a", "b"]
    PAssert.that(output).containsInAnyOrder(
        KV.of(1, ImmutableList.of("a")),
        KV.of(1, ImmutableList.of("a", "b"))
    );

    pipeline.run().waitUntilFinish();
  }

  // --- Test 3: Buffer eviction when capacity is exceeded ---
  @Test
  public void testEvictionWhenExceedCapacity() {
    PCollection<KV<Integer, String>> input =
        pipeline
            .apply(Create.of(KV.of(1, "a"), KV.of(1, "b"), KV.of(1, "c"), KV.of(1, "d")))
            .apply(Window.into(FixedWindows.of(Duration.standardMinutes(5))));

    PCollection<KV<Integer, ImmutableList<String>>> output =
        input.apply(ParDo.of(GetLastNElementsDoFn.<Integer, String>create(3)));

    // We expect four outputs (one per element):
    //   1. After "a": ["a"]
    //   2. After "b": ["a", "b"]
    //   3. After "c": ["a", "b", "c"]
    //   4. After "d": oldest ("a") is evicted, resulting in ["b", "c", "d"]
    //
    // Because ordering of outputs in a pipeline can be nondeterministic,
    // we use a custom assertion to verify the sequence for key 1.
    PAssert.that(output)
        .satisfies(iterable -> {
          // Collect outputs into a list.
          List<KV<Integer, ImmutableList<String>>> outputs = 
              ImmutableList.copyOf(iterable);
          // For the DirectRunner and Create transform the order is preserved.
          // Adjust the assertions if you run with a runner that reorders elements.
          assertEquals(4, outputs.size());
          assertEquals(ImmutableList.of("a"), outputs.get(0).getValue());
          assertEquals(ImmutableList.of("a", "b"), outputs.get(1).getValue());
          assertEquals(ImmutableList.of("a", "b", "c"), outputs.get(2).getValue());
          assertEquals(ImmutableList.of("b", "c", "d"), outputs.get(3).getValue());
          return null;
        });

    pipeline.run().waitUntilFinish();
  }

  // --- Test 4: Multiple keys state isolation ---
  @Test
  public void testMultipleKeysStateIsolation() {
    PCollection<KV<Integer, String>> input =
        pipeline
            .apply(Create.of(KV.of(1, "a"), KV.of(2, "x")))
            .apply(Window.into(FixedWindows.of(Duration.standardMinutes(5))));

    PCollection<KV<Integer, ImmutableList<String>>> output =
        input.apply(ParDo.of(GetLastNElementsDoFn.<Integer, String>create(3)));

    // Expect one output for key 1 and one for key 2
    PAssert.that(output).containsInAnyOrder(
        KV.of(1, ImmutableList.of("a")),
        KV.of(2, ImmutableList.of("x"))
    );

    pipeline.run().waitUntilFinish();
  }

  // --- Test 5: Null value should throw an exception ---
  @Test
  public void testNullValueThrowsException() {
    PCollection<KV<Integer, String>> input =
        pipeline
            .apply(Create.<KV<Integer, String>>of(KV.of(1, null)))
            .apply(Window.<KV<Integer, String>>into(FixedWindows.of(Duration.standardMinutes(5))));

    PCollection<KV<Integer, ImmutableList<String>>> output =
        input.apply(ParDo.of(GetLastNElementsDoFn.<Integer, String>create(3)));

    // Running the pipeline should result in a NullPointerException
    assertThrows(NullPointerException.class, () -> {
      pipeline.run().waitUntilFinish();
    });
  }

  // --- Test 6: Zero capacity should throw an exception ---
  @Test
  public void testZeroCapacityThrowsException() {
      // Simply assert that creating a DoFn with zero capacity throws an exception.
      assertThrows(IllegalArgumentException.class, () -> {
          GetLastNElementsDoFn.<Integer, String>create(0);
      });
  }
}
