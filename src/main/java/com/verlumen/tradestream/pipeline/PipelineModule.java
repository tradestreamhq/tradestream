package com.verlumen.tradestream.pipeline;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.verlumen.tradestream.kafka.KafkaReadTransform;

@AutoValue
abstract class PipelineModule extends AbstractModule {
  static PipelineModule create(
    String bootstrapServers, String candleTopic, int intervalHours) {
    return new AutoValue_PipelineModule();
  }

  abstract String bootstrapServers();
  abstract String candleTopic();
  abstract int dynamicReadIntervalHours();

  @Override
  protected void configure() {}

  @Provides
  KafkaReadTransform provideKafkaReadTransform() {
    return KafkaReadTransform.builder()
      .setBootstrapServers(bootstrapServers())
      .setTopic(candleTopic())
      .setDynamicReadIntervalHours(dynamicReadIntervalHours())
      .build();
  }
}
