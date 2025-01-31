package com.verlumen.tradestream.kafka;

import com.google.inject.Inject;
import com.verlumen.tradestream.execution.RunMode;
import org.apache.kafka.common.serialization.Deserializer;

final class KafkaReadTransformFactory implements KafkaReadTransform.Factory {
  private final KafkaProperties kafkaProperties;
  private final RunMode runMode;

  @Inject
  KafkaReadTransformFactory(KafkaProperties kafkaProperties, RunMode runMode) {
    this.kafkaProperties = kafkaProperties;
    this.runMode = runMode;
  }

  /**
   * Returns a KafkaReadTransform, either the "dry-run" version or the real version,
   * depending on the current RunMode. Both are parameterized by K, V.
   */
  @Override
  public <K, V> KafkaReadTransform<K, V> create(
      String topic,
      Class<? extends Deserializer<? super K>> keyDeserializer,
      Class<? extends Deserializer<? super V>> valueDeserializer
  ) {

    // If you're in "dry run" mode, use the DryRunKafkaReadTransform builder
    if (runMode.equals(RunMode.DRY)) {
      return DryRunKafkaReadTransform
          .<K, V>builder()
          .setBootstrapServers(kafkaProperties.bootstrapServers())
          .setTopic(topic)
          // (Assuming DryRunKafkaReadTransform is also generic and has these methods)
          .setKeyDeserializerClass((Class) keyDeserializer)
          .setValueDeserializerClass((Class) valueDeserializer)
          .build();
    }

    // Otherwise, use the real KafkaReadTransformImpl
    return KafkaReadTransformImpl
        .<K, V>builder()
        .setBootstrapServers(kafkaProperties.bootstrapServers())
        .setTopic(topic)
        .setKeyDeserializerClass((Class) keyDeserializer)
        .setValueDeserializerClass((Class) valueDeserializer)
        .build();
  }
}
