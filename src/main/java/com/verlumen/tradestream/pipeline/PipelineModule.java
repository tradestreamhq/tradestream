package com.verlumen.tradestream.pipeline;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.verlumen.tradestream.execution.ExecutionModule;
import com.verlumen.tradestream.kafka.KafkaModule;
import com.verlumen.tradestream.kafka.KafkaReadTransform;

@AutoValue
abstract class PipelineModule extends AbstractModule {
  static PipelineModule create(
    String bootstrapServers, String candleTopic, int intervalHours, String runMode) {
    return new AutoValue_PipelineModule(bootstrapServers, candleTopic, intervalHours, runMode);
  }

  abstract String bootstrapServers();
  abstract String candleTopic();
  abstract int dynamicReadIntervalHours();
  abstract String runMode();

  @Override
  protected void configure() {
    install(ExecutionModule.create(runMode()));
    install(KafkaModule.create());
  }

  @Provides
  KafkaReadTransform provideKafkaReadTransform(KafkaReadTransform.Factory factory) {
    return factory.create(candleTopic());
  }
}
