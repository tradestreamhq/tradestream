package com.verluem.tradestream.kafka;

import com.google.inject.Inject;

public class KafkaReadTransformFactory implements KafkaReadTransform.Factory {
  private final KafkaProperties kafkaProperties;

  @Inject
  KafkaReadTransformFactory(KafkaProperties kafkaProperties) {
    this.kafkaProperties = kafkaProperties;
  }

  public KafkaReadTransform provideKafkaReadTransform(String topic) {
    return KafkaReadTransformImpl.builder()
      .setBootstrapServers(kafkaProperties.bootstrapServers())
      .setTopic(topic)
      .build();
  }
}
