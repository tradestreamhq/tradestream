package com.verluem.tradestream.kafka;

import com.google.inject.Inject;

final class KafkaReadTransformFactory implements KafkaReadTransform.Factory {
  private final KafkaProperties kafkaProperties;

  @Inject
  KafkaReadTransformFactory(KafkaProperties kafkaProperties) {
    this.kafkaProperties = kafkaProperties;
  }

  @Override
  public KafkaReadTransform create(String topic) {
    return KafkaReadTransformImpl.builder()
      .setBootstrapServers(kafkaProperties.bootstrapServers())
      .setTopic(topic)
      .build();
  }
}
