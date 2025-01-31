package com.verlumen.tradestream.kafka;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableMap;
import org.apache.beam.sdk.coders.ByteArrayCoder;
import org.apache.beam.sdk.coders.Coder;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.beam.sdk.io.kafka.KafkaIO;
import org.apache.beam.sdk.io.kafka.KafkaRecord;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.TypeDescriptor;
import org.apache.kafka.common.serialization.Deserializer;
import org.apache.kafka.common.serialization.ByteArrayDeserializer;
import org.apache.kafka.common.serialization.StringDeserializer;

import java.util.Collections;
import java.util.Map;

/**
 * Generic implementation of Kafka read transform, allowing the user to specify
 * K (the key type) and V (the value type) plus their deserializers.
 */
@AutoValue
abstract class KafkaReadTransformImpl<K, V> extends KafkaReadTransform<K, V> {
  private static final ImmutableMap<Class<? extends Deserializer<?>>, Coder<?>> DESERIALIZER_TO_CODER_MAP =
      ImmutableMap.<Class<? extends Deserializer<?>>, Coder<?>>builder()
          .put(StringDeserializer.class, StringUtf8Coder.of())
          .put(ByteArrayDeserializer.class, ByteArrayCoder.of())
          .build();

    abstract String bootstrapServers();
    abstract String topic();
    abstract Map<String, Object> consumerConfig();
    abstract Class<? extends Deserializer<K>> keyDeserializerClass();
    abstract Class<? extends Deserializer<V>> valueDeserializerClass();

    Coder<K> keyCoder() {
        return getCoderForDeserializer(keyDeserializerClass());
    }

    Coder<V> valueCoder() {
        return getCoderForDeserializer(valueDeserializerClass());
    }

    static <K, V> Builder<K, V> builder() {
        return new AutoValue_KafkaReadTransformImpl.Builder<K, V>()
            .setConsumerConfig(Collections.emptyMap());
    }

    @AutoValue.Builder
    abstract static class Builder<K, V> {
        abstract Builder<K, V> setBootstrapServers(String bootstrapServers);
        abstract Builder<K, V> setTopic(String topic);
        abstract Builder<K, V> setConsumerConfig(Map<String, Object> consumerConfig);
        abstract Builder<K, V> setKeyDeserializerClass(
            Class<? extends Deserializer<K>> keyDeserializerClass);
        abstract Builder<K, V> setValueDeserializerClass(
            Class<? extends Deserializer<V>> valueDeserializerClass);
        abstract KafkaReadTransformImpl<K, V> build();
    }

    @Override
    public PCollection<V> expand(PBegin input) {
        return input
            .apply("ReadFromKafka", 
                KafkaIO.<K, V>read()
                    .withBootstrapServers(bootstrapServers())
                    .withTopic(topic())
                    .withKeyDeserializerAndCoder(keyDeserializerClass(), keyCoder())
                    .withValueDeserializerAndCoder(valueDeserializerClass(), valueCoder())
                    .withConsumerConfigUpdates(consumerConfig()))
            .apply("ExtractValue",
                MapElements.into(valueCoder().getEncodedTypeDescriptor())
                    .via((KafkaRecord<K, V> record) -> record.getKV().getValue()));
    }

      /**
     * Returns a KafkaReadTransform, parameterized by K, V.
     */
    @SuppressWarnings("unchecked")
    private <T> Coder<T> getCoderForDeserializer(Class<? extends Deserializer<? super T>> deserializerClass) {
        Coder<?> coder = DESERIALIZER_TO_CODER_MAP.get(deserializerClass);
        if (coder == null) {
        throw new IllegalArgumentException(
            String.format("No coder mapping found for deserializer class: %s. Supported deserializers: %s",
                deserializerClass.getName(),
                DESERIALIZER_TO_CODER_MAP.keySet()));
        }
        return (Coder<T>) coder;
    }
}
