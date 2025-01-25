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
import org.joda.time.Duration;

import java.util.Collections;
import java.util.Map;

@AutoValue
public abstract class KafkaReadTransform extends PTransform<PBegin, PCollection<String>> {

  abstract String bootstrapServers();
  abstract String topic();
  abstract int dynamicReadIntervalHours();
  abstract Map<String, Object> consumerConfig();

  public static Builder builder() {
    return new AutoValue_KafkaReadTransform.Builder()
        .setConsumerConfig(Collections.emptyMap()); // default
  }

  @AutoValue.Builder
  public abstract static class Builder {
    public abstract Builder setBootstrapServers(String bootstrapServers);
    public abstract Builder setTopic(String topic);
    public abstract Builder setDynamicReadIntervalHours(int hours);
    public abstract Builder setConsumerConfig(Map<String, Object> consumerConfig);
    public abstract KafkaReadTransform build();
  }

  @Override
  public PCollection<String> expand(PBegin input) {
    Duration interval = Duration.standardHours(dynamicReadIntervalHours());

    // Create the KafkaIO read transform
    KafkaIO.Read<Long, String> kafkaRead =
        KafkaIO.<Long, String>read()
            .withBootstrapServers(bootstrapServers())
            .withTopic(topic())
            .withKeyDeserializer(LongDeserializer.class)
            .withValueDeserializer(StringDeserializer.class)
            .withConsumerConfigUpdates(consumerConfig())
            .withDynamicRead(interval);

    // Apply the read, then map each KafkaRecord<Long,String> to just the String value
    return input
        .apply("ReadFromKafka", kafkaRead)
        .apply("ExtractValue",
            MapElements.into(TypeDescriptors.strings())
                .via((KafkaRecord<Long, String> record) -> record.getKV().getValue()));
  }
}
