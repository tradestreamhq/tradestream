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

@AutoValue
public abstract class KafkaReadTransform extends PTransform<PBegin, PCollection<String>> {
  public static Builder builder() {
    return new AutoValue_KafkaReadTransform.Builder();
  }

  abstract String bootstrapServers();

  abstract int dynamicReadIntervalHours();

  @AutoValue.Builder
  public abstract static class Builder {
    public abstract Builder setBootstrapServers(String bootstrapServers);
    public abstract Builder setDynamicReadIntervalHours(int hours);

    public abstract KafkaReadTransform build();
  }

  @Override
  public PCollection<String> expand(PBegin input) {
    // Convert the integer hours to a Joda Duration:
    Duration interval = Duration.standardHours(dynamicReadIntervalHours());

    return input
      .apply("ReadFromKafka", KafkaIO.<Long, String>read()
          .withDynamicRead(interval)
          // Provide a function if you have some custom checkStopReading logic
          .withCheckStopReadingFn(partition -> false)
          .withBootstrapServers(bootstrapServers())
          .withKeyDeserializer(LongDeserializer.class)
          .withValueDeserializer(StringDeserializer.class)
          // Additional configs if needed (topics, etc.)
      )
      .apply("ExtractValues", Values.<String>create());
  }
}
