package com.verlumen.tradestream.kafka;

import com.google.auto.value.AutoValue;
import org.apache.beam.sdk.io.kafka.KafkaIO;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.TypeDescriptors;
import org.apache.kafka.common.serialization.LongDeserializer;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.beam.sdk.io.kafka.KafkaRecord;

import java.util.Collections;
import java.util.Map;

@AutoValue
abstract class KafkaReadTransformImpl extends KafkaReadTransform {
  abstract String bootstrapServers();
  abstract String topic();
  abstract Map<String, Object> consumerConfig();

  static Builder builder() {
    return new AutoValue_KafkaReadTransformImpl.Builder()
        .setConsumerConfig(Collections.emptyMap()); // default
  }

  @AutoValue.Builder
  abstract static class Builder {
    abstract Builder setBootstrapServers(String bootstrapServers);
    abstract Builder setTopic(String topic);
    abstract Builder setConsumerConfig(Map<String, Object> consumerConfig);
    abstract KafkaReadTransform build();
  }

  @Override
  public PCollection<String> expand(PBegin input) {
    // Create the KafkaIO read transform
    KafkaIO.Read<Long, String> kafkaRead =
        KafkaIO.<Long, String>read()
            .withBootstrapServers(bootstrapServers())
            .withTopic(topic())
            .withKeyDeserializer(LongDeserializer.class)
            .withValueDeserializer(StringDeserializer.class)
            .withConsumerConfigUpdates(consumerConfig());

    // Apply the read, then map each KafkaRecord<Long,String> to just the String value
    return input
        .apply("ReadFromKafka", kafkaRead)
        .apply("ExtractValue",
            MapElements.into(TypeDescriptors.strings())
                .via((KafkaRecord<Long, String> record) -> record.getKV().getValue()));
  }
}
