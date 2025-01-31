package com.verlumen.tradestream.kafka;

import com.google.auto.value.AutoValue;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.TypeDescriptor;
import org.apache.kafka.common.serialization.Deserializer;

import java.util.Collections;
import java.util.List;
import java.util.Map;

@AutoValue
abstract class DryRunKafkaReadTransform<K, V> extends KafkaReadTransform<K, V> {
  abstract String bootstrapServers();
  abstract String topic();
  abstract Map<String, Object> consumerConfig();

  // Add the generic deserializer classes to mirror KafkaReadTransformImpl
  abstract Class<? extends Deserializer<? super K>> keyDeserializerClass();
  abstract Class<? extends Deserializer<? super V>> valueDeserializerClass();

  static <K, V> Builder<K, V> builder() {
    return new AutoValue_DryRunKafkaReadTransform.Builder<K, V>()
        .setConsumerConfig(Collections.emptyMap()); // default
  }

  @AutoValue.Builder
  abstract static class Builder<K, V> {
    abstract Builder<K, V> setBootstrapServers(String bootstrapServers);
    abstract Builder<K, V> setTopic(String topic);
    abstract Builder<K, V> setConsumerConfig(Map<String, Object> consumerConfig);

    // New: set the deserializer classes
    abstract Builder<K, V> setKeyDeserializerClass(
        Class<? extends Deserializer<? super K>> keyDeserializerClass);
    abstract Builder<K, V> setValueDeserializerClass(
        Class<? extends Deserializer<? super V>> valueDeserializerClass);

    abstract DryRunKafkaReadTransform<K, V> build();
  }

  @Override
  public PCollection<V> expand(PBegin input) {
    // For a DRY run, we typically don't produce real data.
    // We'll produce an empty PCollection<V> to keep it truly generic.
    List<V> mockData = Collections.emptyList();

    return input
        .getPipeline()
        .apply("CreateEmptyData", Create.of(mockData))
        // Provide a correct type descriptor for V
        .setTypeDescriptor(new TypeDescriptor<V>() {});
  }
}
