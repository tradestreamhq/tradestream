package com.verlumen.tradestream.kafka;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class KafkaDefaultsTest {

  @Test
  public void bootstrapServers_hasDefaultValue() {
    assertThat(KafkaDefaults.BOOTSTRAP_SERVERS).isEqualTo("localhost:9092");
  }

  @Test
  public void acks_hasDefaultValue() {
    assertThat(KafkaDefaults.ACKS).isEqualTo("all");
  }

  @Test
  public void retries_hasDefaultValue() {
    assertThat(KafkaDefaults.RETRIES).isEqualTo(5);
  }

  @Test
  public void batchSize_hasDefaultValue() {
    assertThat(KafkaDefaults.BATCH_SIZE).isEqualTo(16384);
  }

  @Test
  public void lingerMs_hasDefaultValue() {
    assertThat(KafkaDefaults.LINGER_MS).isEqualTo(50);
  }

  @Test
  public void bufferMemory_hasDefaultValue() {
    assertThat(KafkaDefaults.BUFFER_MEMORY).isEqualTo(33554432);
  }

  @Test
  public void keySerializer_hasDefaultValue() {
    assertThat(KafkaDefaults.KEY_SERIALIZER)
        .isEqualTo("org.apache.kafka.common.serialization.StringSerializer");
  }

  @Test
  public void valueSerializer_hasDefaultValue() {
    assertThat(KafkaDefaults.VALUE_SERIALIZER)
        .isEqualTo("org.apache.kafka.common.serialization.ByteArraySerializer");
  }

  @Test
  public void securityProtocol_hasDefaultValue() {
    assertThat(KafkaDefaults.SECURITY_PROTOCOL).isEqualTo("PLAINTEXT");
  }

  @Test
  public void constructor_throwsUnsupportedOperationException() throws Exception {
    Constructor<KafkaDefaults> constructor = KafkaDefaults.class.getDeclaredConstructor();
    constructor.setAccessible(true);

    InvocationTargetException exception =
        assertThrows(InvocationTargetException.class, () -> constructor.newInstance());

    assertThat(exception.getCause()).isInstanceOf(UnsupportedOperationException.class);
    assertThat(exception.getCause().getMessage())
        .contains("KafkaDefaults is a utility class and cannot be instantiated");
  }

  @Test
  public void batchSize_isPositive() {
    assertThat(KafkaDefaults.BATCH_SIZE).isGreaterThan(0);
  }

  @Test
  public void lingerMs_isNonNegative() {
    assertThat(KafkaDefaults.LINGER_MS).isAtLeast(0);
  }

  @Test
  public void bufferMemory_isPositive() {
    assertThat(KafkaDefaults.BUFFER_MEMORY).isGreaterThan(0);
  }

  @Test
  public void retries_isNonNegative() {
    assertThat(KafkaDefaults.RETRIES).isAtLeast(0);
  }

  @Test
  public void keySerializer_isValidClassName() {
    assertThat(KafkaDefaults.KEY_SERIALIZER).contains("Serializer");
  }

  @Test
  public void valueSerializer_isValidClassName() {
    assertThat(KafkaDefaults.VALUE_SERIALIZER).contains("Serializer");
  }

  @Test
  public void bootstrapServers_containsPort() {
    assertThat(KafkaDefaults.BOOTSTRAP_SERVERS).contains(":");
  }

  @Test
  public void securityProtocol_isValidProtocol() {
    assertThat(KafkaDefaults.SECURITY_PROTOCOL).isAnyOf("PLAINTEXT", "SSL", "SASL_PLAINTEXT", "SASL_SSL");
  }
}
