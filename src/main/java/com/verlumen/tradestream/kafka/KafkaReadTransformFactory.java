package com.verlumen.tradestream.kafka;

import com.google.inject.Inject;

final class KafkaReadTransformFactory implements KafkaReadTransform.Factory {
  private final KafkaProperties kafkaProperties;
  private final RunMode runMode;

  @Inject
  KafkaReadTransformFactory(KafkaProperties kafkaProperties, RunMode runMode) {
    this.kafkaProperties = kafkaProperties;
    this.runMode = runMode;
  }

  @Override
  public KafkaReadTransform create(String topic) {
    if (runMode.equals(runMode.DRY)) {
      return DryRunKafkaReadTransform.builder()
        .setBootstrapServers(kafkaProperties.bootstrapServers())
        .setTopic(topic)
        .build();
    }

    return KafkaReadTransformImpl.builder()
      .setBootstrapServers(kafkaProperties.bootstrapServers())
      .setTopic(topic)
      .build();
  }
}
