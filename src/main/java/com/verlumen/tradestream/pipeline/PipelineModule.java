package com.verlumen.tradestream.pipeline;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.verlumen.tradestream.execution.ExecutionModule;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.kafka.DryRunKafkaReadTransform;
import com.verlumen.tradestream.kafka.KafkaModule;
import com.verlumen.tradestream.kafka.KafkaReadTransform;
import java.nio.charset.StandardCharsets;
import org.apache.kafka.common.serialization.ByteArrayDeserializer;
import org.apache.kafka.common.serialization.StringDeserializer;

@AutoValue
abstract class PipelineModule extends AbstractModule {
  static PipelineModule create(
    String bootstrapServers, String candleTopic, String runMode) {
    return new AutoValue_PipelineModule(bootstrapServers, candleTopic, runMode);
  }

  abstract String bootstrapServers();
  abstract String candleTopic();
  abstract String runMode();

  @Override
  protected void configure() {
      install(ExecutionModule.create(runMode()));
      install(KafkaModule.create(bootstrapServers()));
  }

  @Provides
  KafkaReadTransform<String, byte[]> provideKafkaReadTransform(KafkaReadTransform.Factory factory, RunMode runMode) {
      if (runMode.equals(RunMode.DRY)) {
        return DryRunKafkaReadTransform
            .<String, byte[]>builder()
            .setBootstrapServers(kafkaProperties.bootstrapServers())
            .setTopic(candleTopic())
            .setKeyDeserializerClass(StringDeserializer.class)
            .setValueDeserializerClass(ByteArrayDeserializer.class)
            .setDefaultValue("dummy_value".getBytes(StandardCharsets.UTF_8))
            .build();
      }

      return factory.create(
          candleTopic(), 
          StringDeserializer.class,
          ByteArrayDeserializer.class);
  }
}
