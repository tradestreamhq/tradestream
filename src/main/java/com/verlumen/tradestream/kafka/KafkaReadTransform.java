package com.verlumen.tradestream.kafka;

import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;

public abstract class KafkaReadTransform extends PTransform<PBegin, PCollection<String>> {
  public static interface Factory {
    KafkaReadTransform create(String topic);
  }
}
