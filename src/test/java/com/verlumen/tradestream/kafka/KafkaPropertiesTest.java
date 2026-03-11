package com.verlumen.tradestream.kafka;

import static com.google.common.truth.Truth.assertThat;

import java.util.Properties;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class KafkaPropertiesTest {

  @Test
  public void kafkaProperties_withKafkaBootstrapServers_includesBootstrapServersKey() {
    // Arrange
    KafkaProperties supplier =
        new KafkaProperties(
            16384,
            "localhost:9092",
            33554432,
            "org.apache.kafka.common.serialization.StringSerializer",
            "org.apache.kafka.common.serialization.StringSerializer",
            "PLAINTEXT",
            "PLAIN",
            "some.config",
            "all",
            0,
            1);

    // Act
    Properties kafkaProperties = supplier.get();

    // Assert
    assertThat(kafkaProperties.containsKey("bootstrap.servers")).isTrue();
  }

  @Test
  public void kafkaProperties_withKafkaBootstrapServers_removesKafkaPrefixAndRetainsValue() {
    // Arrange
    KafkaProperties supplier =
        new KafkaProperties(
            16384,
            "localhost:9092",
            33554432,
            "org.apache.kafka.common.serialization.StringSerializer",
            "org.apache.kafka.common.serialization.StringSerializer",
            "PLAINTEXT",
            "PLAIN",
            "some.config",
            "all",
            0,
            1);

    // Act
    Properties kafkaProperties = supplier.get();

    // Assert
    assertThat(kafkaProperties.getProperty("bootstrap.servers")).isEqualTo("localhost:9092");
  }

  @Test
  public void testKafkaProperties_includesRetriesAndLinger() {
    // Arrange
    KafkaProperties supplier =
        new KafkaProperties(
            16384,
            "localhost:9092",
            33554432,
            "org.apache.kafka.common.serialization.StringSerializer",
            "org.apache.kafka.common.serialization.StringSerializer",
            "PLAINTEXT",
            "PLAIN",
            "some.config",
            "all",
            50,
            5);
    // Act
    Properties kafkaProps = supplier.get();

    // Assert
    assertThat(kafkaProps.getProperty("acks")).isEqualTo("all");
    assertThat(kafkaProps.getProperty("retries")).isEqualTo("5");
    assertThat(kafkaProps.getProperty("linger.ms")).isEqualTo("50");
  }

  @Test
  public void kafkaProperties_withSaslSsl_includesSaslProperties() {
    // Arrange
    KafkaProperties supplier =
        new KafkaProperties(
            16384,
            "kafka.example.com:9093",
            33554432,
            "org.apache.kafka.common.serialization.StringSerializer",
            "org.apache.kafka.common.serialization.ByteArraySerializer",
            "SASL_SSL",
            "SCRAM-SHA-256",
            "org.apache.kafka.common.security.scram.ScramLoginModule required username=\"user\""
                + " password=\"pass\";",
            "all",
            50,
            5);

    // Act
    Properties kafkaProps = supplier.get();

    // Assert
    assertThat(kafkaProps.getProperty("security.protocol")).isEqualTo("SASL_SSL");
    assertThat(kafkaProps.getProperty("sasl.mechanism")).isEqualTo("SCRAM-SHA-256");
    assertThat(kafkaProps.getProperty("sasl.jaas.config")).contains("ScramLoginModule");
  }

  @Test
  public void kafkaProperties_withPlaintext_omitsSaslProperties() {
    // Arrange
    KafkaProperties supplier =
        new KafkaProperties(
            16384,
            "localhost:9092",
            33554432,
            "org.apache.kafka.common.serialization.StringSerializer",
            "org.apache.kafka.common.serialization.ByteArraySerializer",
            "PLAINTEXT",
            "",
            "",
            "all",
            50,
            5);

    // Act
    Properties kafkaProps = supplier.get();

    // Assert
    assertThat(kafkaProps.getProperty("security.protocol")).isEqualTo("PLAINTEXT");
    assertThat(kafkaProps.containsKey("sasl.mechanism")).isFalse();
    assertThat(kafkaProps.containsKey("sasl.jaas.config")).isFalse();
  }
}
