package com.verlumen.tradestream.kafka;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertEquals;

import com.google.testing.junit.testparameterinjector.TestParameterInjector;
import java.util.Collections;
import java.util.Map;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(TestParameterInjector.class)
public class KafkaReadTransformImplTest {

  @Test
  public void builder_minimalConfiguration() {
    // Arrange
    String bootstrapServers = "localhost:9092";
    String topic = "test-topic";

    // Act
    // Now we specify <String, String> for K, V and set
    // deserializer classes to StringDeserializer.
    KafkaReadTransformImpl<String, String> transform =
        KafkaReadTransformImpl.<String, String>builder()
            .setBootstrapServers(bootstrapServers)
            .setTopic(topic)
            .setKeyDeserializerClass(StringDeserializer.class)
            .setValueDeserializerClass(StringDeserializer.class)
            .build();

    // Assert
    assertThat(transform.bootstrapServers()).isEqualTo(bootstrapServers);
    assertThat(transform.topic()).isEqualTo(topic);
    // By default, consumerConfig() should be empty
    assertThat(transform.consumerConfig()).isEqualTo(Collections.emptyMap());
  }

  @Test
  public void builder_withConsumerConfig() {
    // Arrange
    String bootstrapServers = "broker1:9092,broker2:9092";
    String topic = "another-topic";
    Map<String, Object> consumerConfig = Map.of(
        "group.id", "test-group",
        "auto.offset.reset", "earliest"
    );

    // Act
    // Same approach, specify the generic types and deserializers.
    KafkaReadTransformImpl<String, String> transform =
        KafkaReadTransformImpl.<String, String>builder()
            .setBootstrapServers(bootstrapServers)
            .setTopic(topic)
            .setConsumerConfig(consumerConfig)
            .setKeyDeserializerClass(StringDeserializer.class)
            .setValueDeserializerClass(StringDeserializer.class)
            .build();

    // Assert
    assertThat(transform.bootstrapServers()).isEqualTo(bootstrapServers);
    assertThat(transform.topic()).isEqualTo(topic);
    assertThat(transform.consumerConfig()).isEqualTo(consumerConfig);
  }

  @Test
  public void defaultConsumerConfig_isInitiallyEmpty() {
    // Arrange
    // Minimal builder calls, plus the required deserializer classes.
    KafkaReadTransformImpl<String, String> transform =
        KafkaReadTransformImpl.<String, String>builder()
            .setBootstrapServers("some-servers")
            .setTopic("a-topic")
            .setKeyDeserializerClass(StringDeserializer.class)
            .setValueDeserializerClass(StringDeserializer.class)
            .build();

    // Act / Assert
    assertThat(transform.consumerConfig()).isEqualTo(Collections.emptyMap());
  }

  // Optionally, if you want to confirm the deserializer classes were stored:
  @Test
  public void keyAndValueDeserializer_areAsExpected() {
    KafkaReadTransformImpl<String, String> transform =
        KafkaReadTransformImpl.<String, String>builder()
            .setBootstrapServers("some-servers")
            .setTopic("a-topic")
            .setKeyDeserializerClass(StringDeserializer.class)
            .setValueDeserializerClass(StringDeserializer.class)
            .build();

    // Example of checking the actual class references
    assertThat(transform.keyDeserializerClass()).isEqualTo(StringDeserializer.class);
    assertThat(transform.valueDeserializerClass()).isEqualTo(StringDeserializer.class);
  }
}
