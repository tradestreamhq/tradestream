package com.verlumen.tradestream.kafka;

import com.google.common.collect.ImmutableMap;
import com.google.inject.Inject;
import org.apache.beam.sdk.coders.ByteArrayCoder;
import org.apache.beam.sdk.coders.Coder;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.kafka.common.serialization.ByteArrayDeserializer;
import org.apache.kafka.common.serialization.Deserializer;
import org.apache.kafka.common.serialization.StringDeserializer;

import java.util.Map;

final class KafkaReadTransformFactory implements KafkaReadTransform.Factory {
  private final KafkaProperties kafkaProperties;
  
  private static final Map<Class<? extends Deserializer<?>>, Coder<?>> DESERIALIZER_TO_CODER_MAP =
      ImmutableMap.<Class<? extends Deserializer<?>>, Coder<?>>builder()
          .put(StringDeserializer.class, StringUtf8Coder.of())
          .put(ByteArrayDeserializer.class, ByteArrayCoder.of())
          .build();

  @Inject
  KafkaReadTransformFactory(KafkaProperties kafkaProperties) {
    this.kafkaProperties = kafkaProperties;
  }

  /**
   * Returns a KafkaReadTransform, either the "dry-run" version or the real version,
   * depending on the current RunMode. Both are parameterized by K, V.
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

  @Override
  public <K, V> KafkaReadTransform<K, V> create(
      String topic,
      Class<? extends Deserializer<? super K>> keyDeserializer,
      Class<? extends Deserializer<? super V>> valueDeserializer) {
    return KafkaReadTransformImpl
        .<K, V>builder()
        .setBootstrapServers(kafkaProperties.bootstrapServers())
        .setTopic(topic)
        .setKeyDeserializerClass((Class) keyDeserializer)
        .setValueDeserializerClass((Class) valueDeserializer)
        .setKeyCoder(getCoderForDeserializer(keyDeserializer))
        .setValueCoder(getCoderForDeserializer(valueDeserializer))
        .build();
  }
}
