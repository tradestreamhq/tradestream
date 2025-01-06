package com.verlumen.tradestream.kafka;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableMap;
import java.util.Map;
import java.util.Properties;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class KafkaPropertiesTest {

  @Test
  public void kafkaProperties_withKafkaBootstrapServers_includesBootstrapServersKey() {
    // Arrange
    Map<String, String> inputProperties = ImmutableMap.of(
        "kafka.bootstrap.servers", "localhost:9092",
        "application.name", "TestApp"
    );
    KafkaProperties supplier = KafkaProperties.createFromKafkaPrefixedProperties(inputProperties);

    // Act
    Properties kafkaProperties = supplier.get();

    // Assert
    assertThat(kafkaProperties.containsKey("bootstrap.servers")).isTrue();
  }

  @Test
  public void kafkaProperties_withKafkaClientId_includesClientIdKey() {
    // Arrange
    Map<String, String> inputProperties = ImmutableMap.of(
        "kafka.client.id", "client-1",
        "application.name", "TestApp"
    );
    KafkaProperties supplier = KafkaProperties.createFromKafkaPrefixedProperties(inputProperties);

    // Act
    Properties kafkaProperties = supplier.get();

    // Assert
    assertThat(kafkaProperties.containsKey("client.id")).isTrue();
  }

  @Test
  public void kafkaProperties_withNonKafkaProperty_excludesNonKafkaKey() {
    // Arrange
    Map<String, String> inputProperties = ImmutableMap.of(
        "application.name", "TestApp"
    );
    KafkaProperties supplier = KafkaProperties.createFromKafkaPrefixedProperties(inputProperties);

    // Act
    Properties kafkaProperties = supplier.get();

    // Assert
    assertThat(kafkaProperties.containsKey("application.name")).isFalse();
  }

  @Test
  public void kafkaProperties_withKafkaBootstrapServers_removesKafkaPrefixAndRetainsValue() {
    // Arrange
    Map<String, String> inputProperties = ImmutableMap.of(
        "kafka.bootstrap.servers", "localhost:9092"
    );
    KafkaProperties supplier = KafkaProperties.createFromKafkaPrefixedProperties(inputProperties);

    // Act
    Properties kafkaProperties = supplier.get();

    // Assert
    assertThat(kafkaProperties.getProperty("bootstrap.servers")).isEqualTo("localhost:9092");
  }

  @Test
  public void kafkaProperties_withKafkaClientId_removesKafkaPrefixAndRetainsValue() {
    // Arrange
    Map<String, String> inputProperties = ImmutableMap.of(
        "kafka.client.id", "client-1"
    );
    KafkaProperties supplier = KafkaProperties.createFromKafkaPrefixedProperties(inputProperties);

    // Act
    Properties kafkaProperties = supplier.get();

    // Assert
    assertThat(kafkaProperties.getProperty("client.id")).isEqualTo("client-1");
  }

  @Test
  public void kafkaProperties_withNoInput_returnsEmptyProperties() {
    // Arrange
    Map<String, String> inputProperties = ImmutableMap.of();
    KafkaProperties supplier = KafkaProperties.createFromKafkaPrefixedProperties(inputProperties);

    // Act
    Properties kafkaProperties = supplier.get();

    // Assert
    assertThat(kafkaProperties.isEmpty()).isTrue();
  }

  @Test
  public void kafkaProperties_withNoKafkaProperties_returnsEmptyProperties() {
    // Arrange
    Map<String, String> inputProperties = ImmutableMap.of(
        "application.name", "TestApp"
    );
    KafkaProperties supplier = KafkaProperties.createFromKafkaPrefixedProperties(inputProperties);

    // Act
    Properties kafkaProperties = supplier.get();

    // Assert
    assertThat(kafkaProperties.isEmpty()).isTrue();
  }

  @Test
  public void testKafkaProperties_includesRetriesAndLinger() {
    // Arrange
    Map<String, String> inputProperties = ImmutableMap.of(
        "kafka.acks", "all",
        "kafka.retries", "5",
        "kafka.linger.ms", "50"
    );
    KafkaProperties supplier = KafkaProperties.createFromKafkaPrefixedProperties(inputProperties);

    // Act
    Properties kafkaProps = supplier.get();

    // Assert
    assertThat(kafkaProps.getProperty("acks")).isEqualTo("all");
    assertThat(kafkaProps.getProperty("retries")).isEqualTo("5");
    assertThat(kafkaProps.getProperty("linger.ms")).isEqualTo("50");
  }
}
