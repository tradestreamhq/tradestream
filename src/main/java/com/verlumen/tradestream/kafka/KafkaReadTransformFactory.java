package com.verluem.tradestream.kafka;

public class KafkaReadTransformFactoryImpl implements KafkaReadTransform.Factory {
  private final KafkaProperties kafkaProperties;

  @Inject
  KafkaReadTransformFactoryImpl(KafkaProperties kafkaProperties) {
    this.kafkaProperties = kafkaProperties;
  }

  public KafkaReadTransform provideKafkaReadTransform() {
    return KafkaReadTransformImpl.builder()
      .setBootstrapServers(kafkaProperties.bootstrapServers())
      .setTopic()
      .build();
  }
}
