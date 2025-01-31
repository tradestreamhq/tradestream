package com.verlumen.tradestream.kafka;

import com.google.auto.value.AutoValue;
import org.apache.beam.sdk.io.kafka.KafkaIO;
import org.apache.beam.sdk.io.kafka.KafkaRecord;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.TypeDescriptor;
import org.apache.kafka.common.serialization.Deserializer;

import java.util.Collections;
import java.util.Map;

/**
 * Generic implementation of Kafka read transform, allowing the user to specify
 * K (the key type) and V (the value type) plus their deserializers.
 */
@AutoValue
abstract class KafkaReadTransformImpl<K, V> extends KafkaReadTransform<K, V> {
  abstract String bootstrapServers();
  abstract String topic();
  abstract Map<String, Object> consumerConfig();

  // Deserializer classes for key and value. Must be Deserializer<K> and Deserializer<V> specifically.
  abstract Class<? extends Deserializer<K>> keyDeserializerClass();
  abstract Class<? extends Deserializer<V>> valueDeserializerClass();

  /**
   * Builder entry point for creating the transform.
   */
  static <K, V> Builder<K, V> builder() {
    return new AutoValue_KafkaReadTransformImpl.Builder<K, V>()
        .setConsumerConfig(Collections.emptyMap());
  }

  @AutoValue.Builder
  abstract static class Builder<K, V> {
    abstract Builder<K, V> setBootstrapServers(String bootstrapServers);
    abstract Builder<K, V> setTopic(String topic);
    abstract Builder<K, V> setConsumerConfig(Map<String, Object> consumerConfig);

    // Methods to set the deserializer classes
    abstract Builder<K, V> setKeyDeserializerClass(
        Class<? extends Deserializer<K>> keyDeserializerClass);

    abstract Builder<K, V> setValueDeserializerClass(
        Class<? extends Deserializer<V>> valueDeserializerClass);

    abstract KafkaReadTransformImpl<K, V> build();
  }

  @Override
  public PCollection<V> expand(PBegin input) {
    // Create a generic KafkaIO read transform
    KafkaIO.Read<K, V> kafkaRead =
        KafkaIO.<K, V>read()
            .withBootstrapServers(bootstrapServers())
            .withTopic(topic())
            .withKeyDeserializer(keyDeserializerClass())
            .withValueDeserializer(valueDeserializerClass())
            .withConsumerConfigUpdates(consumerConfig());

    // Apply the read, then map each KafkaRecord<K, V> to its value
    return input
        .apply("ReadFromKafka", kafkaRead)
        .apply("ExtractValue",
            MapElements.into(new TypeDescriptor<V>() {})
                .via((KafkaRecord<K, V> record) -> record.getKV().getValue()));
  }
}
