package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import net.sourceforge.argparse4j.inf.Namespace;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

import java.util.HashMap;
import java.util.Map;
import java.util.Properties;

@RunWith(JUnit4.class)
public class KafkaPropertiesTest {
  private static final Map<String, Object> INPUT_PROPERTIES = new HashMap<>();

  @Bind private static final Namespace NAMESPACE = new Namespace(INPUT_PROPERTIES);

  @Inject private KafkaProperties supplier;

  @Before
  public void setup() {
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }

  @After
  public void teardown() {
    INPUT_PROPERTIES.clear();
  }

  // --- Tests for presence of keys ---
  
  @Test
  public void kafkaProperties_withKafkaBootstrapServers_includesBootstrapServersKey() {
    // Arrange
    INPUT_PROPERTIES.put("kafka.bootstrap.servers", "localhost:9092");
    INPUT_PROPERTIES.put("application.name", "TestApp");
    // Act
    Properties kafkaProperties = supplier.get();
    // Assert
    assertThat(kafkaProperties.containsKey("bootstrap.servers")).isTrue();
  }

  @Test
  public void kafkaProperties_withKafkaClientId_includesClientIdKey() {
    // Arrange
    INPUT_PROPERTIES.put("kafka.client.id", "client-1");
    INPUT_PROPERTIES.put("application.name", "TestApp");
    // Act
    Properties kafkaProperties = supplier.get();
    // Assert
    assertThat(kafkaProperties.containsKey("client.id")).isTrue();
  }

  @Test
  public void kafkaProperties_withNonKafkaProperty_excludesNonKafkaKey() {
    // Arrange
    INPUT_PROPERTIES.put("application.name", "TestApp");
    // Act
    Properties kafkaProperties = supplier.get();
    // Assert
    assertThat(kafkaProperties.containsKey("application.name")).isFalse();
  }

  // --- Tests for prefix removal and correct property values ---
  
  @Test
  public void kafkaProperties_withKafkaBootstrapServers_removesKafkaPrefixAndRetainsValue() {
    // Arrange
    INPUT_PROPERTIES.put("kafka.bootstrap.servers", "localhost:9092");
    // Act
    Properties kafkaProperties = supplier.get();
    // Assert
    assertThat(kafkaProperties.getProperty("bootstrap.servers")).isEqualTo("localhost:9092");
  }

  @Test
  public void kafkaProperties_withKafkaClientId_removesKafkaPrefixAndRetainsValue() {
    // Arrange
    INPUT_PROPERTIES.put("kafka.client.id", "client-1");
    // Act
    Properties kafkaProperties = supplier.get();
    // Assert
    assertThat(kafkaProperties.getProperty("client.id")).isEqualTo("client-1");
  }

  // --- Tests for empty or no Kafka properties ---
  
  @Test
  public void kafkaProperties_withNoInput_returnsEmptyProperties() {
    // Act
    Properties kafkaProperties = supplier.get();
    // Assert
    assertThat(kafkaProperties.isEmpty()).isTrue();
  }

  @Test
  public void kafkaProperties_withNoKafkaProperties_returnsEmptyProperties() {
    // Arrange
    INPUT_PROPERTIES.put("application.name", "TestApp");
    // Act
    Properties kafkaProperties = supplier.get();
    // Assert
    assertThat(kafkaProperties.isEmpty()).isTrue();
  }

  @Test
  public void testKafkaProperties_includesRetriesAndLinger() {
    INPUT_PROPERTIES.put("kafka.acks", "all");
    INPUT_PROPERTIES.put("kafka.retries", "5");
    INPUT_PROPERTIES.put("kafka.linger.ms", "50");

    Properties kafkaProps = supplier.get();
    assertThat(kafkaProps.getProperty("acks")).isEqualTo("all");
    assertThat(kafkaProps.getProperty("retries")).isEqualTo("5");
    assertThat(kafkaProps.getProperty("linger.ms")).isEqualTo("50");
  }
}
