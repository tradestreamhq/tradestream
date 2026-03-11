package com.verlumen.tradestream.kafka;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import java.util.Properties;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class KafkaPropertiesTest {

  private static KafkaProperties createSslProperties(
      String truststoreLocation, String truststorePassword) {
    return new KafkaProperties(
        16384,
        "localhost:9092",
        33554432,
        "org.apache.kafka.common.serialization.StringSerializer",
        "org.apache.kafka.common.serialization.StringSerializer",
        "SSL",
        "",
        "",
        "all",
        0,
        1,
        truststoreLocation,
        truststorePassword,
        "",
        "",
        "");
  }

  private static KafkaProperties createPlaintextProperties() {
    return new KafkaProperties(
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
        1,
        "",
        "",
        "",
        "",
        "");
  }

  @Test
  public void kafkaProperties_withKafkaBootstrapServers_includesBootstrapServersKey() {
    KafkaProperties supplier = createSslProperties("/path/to/truststore.jks", "password");

    Properties kafkaProperties = supplier.get();

    assertThat(kafkaProperties.containsKey("bootstrap.servers")).isTrue();
  }

  @Test
  public void kafkaProperties_withKafkaBootstrapServers_removesKafkaPrefixAndRetainsValue() {
    KafkaProperties supplier = createSslProperties("/path/to/truststore.jks", "password");

    Properties kafkaProperties = supplier.get();

    assertThat(kafkaProperties.getProperty("bootstrap.servers")).isEqualTo("localhost:9092");
  }

  @Test
  public void testKafkaProperties_includesRetriesAndLinger() {
    KafkaProperties supplier =
        new KafkaProperties(
            16384,
            "localhost:9092",
            33554432,
            "org.apache.kafka.common.serialization.StringSerializer",
            "org.apache.kafka.common.serialization.StringSerializer",
            "SSL",
            "PLAIN",
            "some.config",
            "all",
            50,
            5,
            "/path/to/truststore.jks",
            "password",
            "",
            "",
            "");

    Properties kafkaProps = supplier.get();

    assertThat(kafkaProps.getProperty("acks")).isEqualTo("all");
    assertThat(kafkaProps.getProperty("retries")).isEqualTo("5");
    assertThat(kafkaProps.getProperty("linger.ms")).isEqualTo("50");
  }

  @Test
  public void testKafkaProperties_sslProtocol_setsSslProperties() {
    KafkaProperties supplier =
        new KafkaProperties(
            16384,
            "localhost:9092",
            33554432,
            "org.apache.kafka.common.serialization.StringSerializer",
            "org.apache.kafka.common.serialization.StringSerializer",
            "SSL",
            "",
            "",
            "all",
            0,
            1,
            "/path/to/truststore.jks",
            "trustpass",
            "/path/to/keystore.jks",
            "keypass",
            "keypassword");

    Properties kafkaProps = supplier.get();

    assertThat(kafkaProps.getProperty("security.protocol")).isEqualTo("SSL");
    assertThat(kafkaProps.getProperty("ssl.truststore.location"))
        .isEqualTo("/path/to/truststore.jks");
    assertThat(kafkaProps.getProperty("ssl.truststore.password")).isEqualTo("trustpass");
    assertThat(kafkaProps.getProperty("ssl.keystore.location")).isEqualTo("/path/to/keystore.jks");
    assertThat(kafkaProps.getProperty("ssl.keystore.password")).isEqualTo("keypass");
    assertThat(kafkaProps.getProperty("ssl.key.password")).isEqualTo("keypassword");
  }

  @Test
  public void testKafkaProperties_plaintextProtocol_doesNotSetSslProperties() {
    KafkaProperties supplier = createPlaintextProperties();

    Properties kafkaProps = supplier.get();

    assertThat(kafkaProps.getProperty("security.protocol")).isEqualTo("PLAINTEXT");
    assertThat(kafkaProps.containsKey("ssl.truststore.location")).isFalse();
    assertThat(kafkaProps.containsKey("ssl.keystore.location")).isFalse();
  }

  @Test
  public void testKafkaProperties_sslProtocol_missingTruststore_throwsException() {
    KafkaProperties supplier = createSslProperties("", "");

    assertThrows(IllegalStateException.class, supplier::get);
  }

  @Test
  public void testKafkaProperties_sslProtocol_nullTruststore_throwsException() {
    KafkaProperties supplier =
        new KafkaProperties(
            16384,
            "localhost:9092",
            33554432,
            "org.apache.kafka.common.serialization.StringSerializer",
            "org.apache.kafka.common.serialization.StringSerializer",
            "SSL",
            "",
            "",
            "all",
            0,
            1,
            null,
            "",
            "",
            "",
            "");

    assertThrows(IllegalStateException.class, supplier::get);
  }

  @Test
  public void testKafkaProperties_saslSslProtocol_setsSslProperties() {
    KafkaProperties supplier =
        new KafkaProperties(
            16384,
            "localhost:9092",
            33554432,
            "org.apache.kafka.common.serialization.StringSerializer",
            "org.apache.kafka.common.serialization.StringSerializer",
            "SASL_SSL",
            "PLAIN",
            "some.jaas.config",
            "all",
            0,
            1,
            "/path/to/truststore.jks",
            "trustpass",
            "",
            "",
            "");

    Properties kafkaProps = supplier.get();

    assertThat(kafkaProps.getProperty("security.protocol")).isEqualTo("SASL_SSL");
    assertThat(kafkaProps.getProperty("ssl.truststore.location"))
        .isEqualTo("/path/to/truststore.jks");
    assertThat(kafkaProps.getProperty("ssl.truststore.password")).isEqualTo("trustpass");
  }

  @Test
  public void testKafkaProperties_create_defaultsToSsl() {
    KafkaProperties supplier = KafkaProperties.create("localhost:9092");

    assertThat(supplier.securityProtocol()).isEqualTo("SSL");
  }
}
