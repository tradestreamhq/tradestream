package com.verlumen.tradestream.kafka;

import com.google.auto.value.AutoValue;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.TypeDescriptors;

import java.util.Collections;
import java.util.List;
import java.util.Map;

@AutoValue
abstract class DryRunKafkaReadTransform extends KafkaReadTransform {
  abstract String bootstrapServers();
  abstract String topic();
  abstract Map<String, Object> consumerConfig();

  static Builder builder() {
    return new AutoValue_DryRunKafkaReadTransform.Builder()
        .setConsumerConfig(Collections.emptyMap()); // default
  }

  @AutoValue.Builder
  abstract static class Builder {
    abstract Builder setBootstrapServers(String bootstrapServers);
    abstract Builder setTopic(String topic);
    abstract Builder setConsumerConfig(Map<String, Object> consumerConfig);
    abstract DryRunKafkaReadTransform build();
  }

  @Override
  public PCollection<String> expand(PBegin input) {
    // Create a list of strings to simulate the Kafka read
    List<String> mockData = List.of(
        "hello",
        "world",
        "bootstrapServers: " + bootstrapServers(),
        "topic: " + topic(),
        "consumerConfig: " + consumerConfig().toString()
    );

    // Return the mock data as a PCollection
    return input.getPipeline()
        .apply("CreateMockData", Create.of(mockData))
        .setTypeDescriptor(TypeDescriptors.strings());
  }
}
