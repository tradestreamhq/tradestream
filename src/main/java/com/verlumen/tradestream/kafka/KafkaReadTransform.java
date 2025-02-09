package com.verlumen.tradestream.kafka;

import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;
import org.apache.kafka.common.serialization.Deserializer;

/**
 * Now generic on K (key) and V (value).
 */
public abstract class KafkaReadTransform<K, V> extends PTransform<PBegin, PCollection<V>> {
    public static interface Factory {
        <K, V> KafkaReadTransform<K, V> create(
            String topic,
            Class<? extends Deserializer<? super K>> keyDeserializer,
            Class<? extends Deserializer<? super V>> valueDeserializer);
    }
}
