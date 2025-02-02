package com.verlumen.tradestream.transforms;

import com.google.common.collect.ImmutableList;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.state.StateId;
import org.apache.beam.sdk.state.StateSpec;
import org.apache.beam.sdk.state.StateSpecs;
import org.apache.beam.sdk.state.ValueState;
import org.apache.beam.sdk.coders.SerializableCoder;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.TypeDescriptor;
import org.apache.commons.collections4.queue.CircularFifoQueue;
import java.io.Serializable;

public class GetLastNElementsDoFn<K, V> extends DoFn<KV<K, V>, KV<K, ImmutableList<V>>> {

  private final int n;

  // Use a ValueState to store our CircularFifoQueue. CircularFifoQueue is Serializable,
  // so we can use SerializableCoder with a proper TypeDescriptor.
  @StateId("buffer")
  private final StateSpec<ValueState<CircularFifoQueue<V>>> bufferSpec =
      StateSpecs.value(
          SerializableCoder.of(new TypeDescriptor<CircularFifoQueue<V>>() {})
      );

  public GetLastNElementsDoFn(int n) {
    this.n = n;
  }

  @ProcessElement
  public void processElement(
      @Element KV<K, V> element,
      @StateId("buffer") ValueState<CircularFifoQueue<V>> state,
      OutputReceiver<KV<K, ImmutableList<V>>> out) {

    // Read the current queue from state; if none exists yet, create one.
    CircularFifoQueue<V> queue = state.read();
    if (queue == null) {
      queue = new CircularFifoQueue<>(n);
    }

    // Add the new element. CircularFifoQueue automatically evicts the oldest element when full.
    queue.add(element.getValue());

    // Write the updated queue back to state.
    state.write(queue);

    // Emit the current collection as an ImmutableList.
    ImmutableList<V> immutableList = ImmutableList.copyOf(queue);
    out.output(KV.of(element.getKey(), immutableList));
  }
}
