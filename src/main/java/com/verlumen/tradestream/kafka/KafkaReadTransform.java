package com.verlumen.tradestream.kafka;

import com.google.auto.value.AutoValue;
import org.apache.beam.sdk.io.kafka.KafkaIO;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.Values;
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

  // (Optional) Additional consumer config to override defaults:
  abstract Map<String, Object> consumerConfig();

  // ---------------------------------------------------------------------------------------------
  // 2. Builder for constructing instances immutably:
  // ---------------------------------------------------------------------------------------------
  public static Builder builder() {
    return new AutoValue_KafkaReadTransform.Builder()
        // Provide a default empty map in case you don't need extra configs:
        .setConsumerConfig(Collections.emptyMap());
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
    // Convert the integer hours to a Joda Duration
    Duration interval = Duration.standardHours(dynamicReadIntervalHours());

    // Build the KafkaIO.Read with your parameters
    KafkaIO.Read<Long, String> kafkaRead = KafkaIO.<Long, String>read()
        .withBootstrapServers(bootstrapServers())
        .withTopic(topic()) // specify the topic name
        .withKeyDeserializer(LongDeserializer.class)
        .withValueDeserializer(StringDeserializer.class)
        // If you need to override/augment consumer configs:
        .withConsumerConfigUpdates(consumerConfig())
        // For dynamic reads (new partitions, etc.):
        .withDynamicRead(interval);

    // If you want a function to decide when to stop reading:
    // .withCheckStopReadingFn(topicPartition -> false);

    return input
        .apply("ReadFromKafka", kafkaRead)
        .apply("ExtractKafkaValues", MapElements.into(TypeDescriptors.strings())
            .via((KafkaRecord<Long, String> record) -> record.getKV().getValue()))
        .apply("ExtractValues", Values.create());
      }
}
