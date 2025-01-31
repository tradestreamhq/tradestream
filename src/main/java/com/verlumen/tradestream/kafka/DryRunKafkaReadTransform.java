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
public abstract class DryRunKafkaReadTransform<K, V> extends KafkaReadTransform<K, V> {
  abstract String bootstrapServers();
  abstract String topic();
  abstract Map<String, Object> consumerConfig();

  // Add the generic deserializer classes to mirror KafkaReadTransformImpl
  abstract Class<? extends Deserializer<? super K>> keyDeserializerClass();
  abstract Class<? extends Deserializer<? super V>> valueDeserializerClass();

  abstract V defaultValue();

  public static <K, V> Builder<K, V> builder() {
    return new AutoValue_DryRunKafkaReadTransform.Builder<K, V>()
        .setConsumerConfig(Collections.emptyMap());
  }

  @AutoValue.Builder
  public abstract static class Builder<K, V> {
    public abstract Builder<K, V> setBootstrapServers(String bootstrapServers);
    public abstract Builder<K, V> setTopic(String topic);
    public abstract Builder<K, V> setConsumerConfig(Map<String, Object> consumerConfig);
    public abstract Builder<K, V> setKeyDeserializerClass(
        Class<? extends Deserializer<? super K>> keyDeserializerClass);
    public abstract Builder<K, V> setValueDeserializerClass(
        Class<? extends Deserializer<? super V>> valueDeserializerClass);

    public abstract Builder<K, V> setDefaultValue(V defaultValue);

    public abstract DryRunKafkaReadTransform<K, V> build();
  }

  @Override
  public PCollection<V> expand(PBegin input) {
    // Create mock data based on the default value.
    List<V> mockData = Collections.singletonList(defaultValue());

    return input
        .getPipeline()
        .apply("CreateMockData", Create.of(mockData))
        .setTypeDescriptor(new TypeDescriptor<V>() {});
  }
}
