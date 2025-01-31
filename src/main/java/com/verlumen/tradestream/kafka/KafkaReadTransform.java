package com.verlumen.tradestream.kafka;

import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;

/**
 * Now generic on K (key) and V (value).
 */
public abstract class KafkaReadTransform<K, V> extends PTransform<PBegin, PCollection<V>> {}
