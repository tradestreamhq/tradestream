package com.verlumen.tradestream.kafka;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertEquals;

import com.google.testing.junit.testparameterinjector.TestParameterInjector;
import java.util.Collections;
import java.util.Map;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(TestParameterInjector.class)
public class KafkaReadTransformTest {

  @Test
  public void builder_minimalConfiguration() {
    // Arrange
    String bootstrapServers = "localhost:9092";
    String topic = "test-topic";
    int intervalHours = 1;

    // Act
    KafkaReadTransform transform =
        KafkaReadTransform.builder()
            .setBootstrapServers(bootstrapServers)
            .setTopic(topic)
            .setDynamicReadIntervalHours(intervalHours)
            .build();

    // Assert
    assertThat(transform.bootstrapServers()).isEqualTo(bootstrapServers);
    assertThat(transform.topic()).isEqualTo(topic);
    assertThat(transform.dynamicReadIntervalHours()).isEqualTo(intervalHours);
    assertThat(transform.consumerConfig()).isEqualTo(Collections.emptyMap()); // Default config
  }

  @Test
  public void builder_withConsumerConfig() {
    // Arrange
    String bootstrapServers = "broker1:9092,broker2:9092";
    String topic = "another-topic";
    int intervalHours = 24;
    Map<String, Object> consumerConfig = Map.of("group.id", "test-group", "auto.offset.reset", "earliest");

    // Act
    KafkaReadTransform transform =
        KafkaReadTransform.builder()
            .setBootstrapServers(bootstrapServers)
            .setTopic(topic)
            .setDynamicReadIntervalHours(intervalHours)
            .setConsumerConfig(consumerConfig)
            .build();

    // Assert
    assertThat(transform.bootstrapServers()).isEqualTo(bootstrapServers);
    assertThat(transform.topic()).isEqualTo(topic);
    assertThat(transform.dynamicReadIntervalHours()).isEqualTo(intervalHours);
    assertThat(transform.consumerConfig()).isEqualTo(consumerConfig);
  }

  @Test
  public void defaultConsumerConfig_isInitiallyEmpty() {
    // Arrange/Act
    KafkaReadTransform transform = KafkaReadTransform.builder()
        .setBootstrapServers("some-servers")
        .setTopic("a-topic")
        .setDynamicReadIntervalHours(1)
        .build();

    // Assert
    assertThat(transform.consumerConfig()).isEqualTo(Collections.emptyMap());
  }

  // Further tests could include validation of parameters if added to the builder,
  // or more complex scenarios if the transform logic itself was more intricate.
  // For now, focusing on verifying the builder and parameter passing.
}
