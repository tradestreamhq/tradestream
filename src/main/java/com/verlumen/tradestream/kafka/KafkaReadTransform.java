package com.verlumen.tradestream.kafka;

import com.google.auto.value.AutoValue;
import org.apache.beam.sdk.io.kafka.KafkaIO;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;
import org.apache.kafka.common.serialization.LongDeserializer;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.joda.time.Duration;

import java.util.Collections;
import java.util.Map;

@AutoValue
public abstract class KafkaReadTransform extends PTransform<PBegin, PCollection<String>> {

  // ---------------------------------------------------------------------------------------------
  // 1. Abstract getters for your config parameters:
  // ---------------------------------------------------------------------------------------------
  abstract String bootstrapServers();
  abstract String topic();
  abstract int dynamicReadIntervalHours();

  // (Optional) Additional consumer config to override defaults
  abstract Map<String, Object> consumerConfig();

  // ---------------------------------------------------------------------------------------------
  // 2. Builder for constructing instances immutably:
  // ---------------------------------------------------------------------------------------------
  public static Builder builder() {
    return new AutoValue_KafkaReadTransform.Builder()
        .setConsumerConfig(Collections.emptyMap()); // Default to empty map
  }

  @AutoValue.Builder
  public abstract static class Builder {
    // Required fields
    public abstract Builder setBootstrapServers(String bootstrapServers);
    public abstract Builder setTopic(String topic);
    public abstract Builder setDynamicReadIntervalHours(int hours);

    // Optional fields
    public abstract Builder setConsumerConfig(Map<String, Object> consumerConfig);

    public abstract KafkaReadTransform build();
  }

  // ---------------------------------------------------------------------------------------------
  // 3. expand() method applying KafkaIO read with your config:
  // ---------------------------------------------------------------------------------------------
  @Override
  public PCollection<String> expand(PBegin input) {
    // Convert int hours to a Joda Duration
    Duration interval = Duration.standardHours(dynamicReadIntervalHours());

    return input.apply(
        "ReadFromKafka",
        KafkaIO.<Long, String>read()
            .withBootstrapServers(bootstrapServers())
            .withTopic(topic()) // specify the topic name
            .withKeyDeserializer(LongDeserializer.class)
            .withValueDeserializer(StringDeserializer.class)
            .withConsumerConfigUpdates(consumerConfig())
            // For dynamic reads (new partitions, etc.)
            .withDynamicRead(interval)
            // Tells Beam to produce PCollection<String> directly.
            .withValueOnly());
  }
}
