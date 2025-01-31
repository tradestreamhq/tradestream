package com.verlumen.tradestream.kafka;

import com.google.inject.Inject;
import org.apache.kafka.common.serialization.Deserializer;

final class KafkaReadTransformFactory implements KafkaReadTransform.Factory {
  private final KafkaProperties kafkaProperties;

  @Inject
  KafkaReadTransformFactory(KafkaProperties kafkaProperties) {
    this.kafkaProperties = kafkaProperties;
  }

  /**
   * Returns a KafkaReadTransform, either the "dry-run" version or the real version,
   * depending on the current RunMode. Both are parameterized by K, V.
   */
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
        .build();
  }
}
