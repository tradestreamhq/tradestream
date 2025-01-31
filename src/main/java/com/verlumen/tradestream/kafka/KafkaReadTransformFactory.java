package com.verlumen.tradestream.kafka;

import com.google.inject.Inject;
import org.apache.beam.sdk.coders.ByteArrayCoder;
import org.apache.beam.sdk.coders.Coder;
import org.apache.beam.sdk.coders.StringUtf8Coder;
import org.apache.kafka.common.serialization.ByteArrayDeserializer;
import org.apache.kafka.common.serialization.Deserializer;
import org.apache.kafka.common.serialization.StringDeserializer;

final class KafkaReadTransformFactory implements KafkaReadTransform.Factory {
  private final KafkaProperties kafkaProperties;

  @Inject
  KafkaReadTransformFactory(KafkaProperties kafkaProperties) {
    this.kafkaProperties = kafkaProperties;
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
        .build();
  }
}
