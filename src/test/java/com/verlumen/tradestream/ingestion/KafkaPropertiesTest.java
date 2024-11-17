package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

import java.util.Properties;

@RunWith(JUnit4.class)
public class KafkaPropertiesTest {
  @Bind private static final Properties INPUT_PROPERTIES = new Properties();

  @Inject private KafkaProperties supplier;

  @Before
  public void setup() {
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }

  @After
  public void teardown() {
    INPUT_PROPERTIES.clear();
  }

  @Test
  public void testExtractKafkaProperties_containsOnlyKafkaProperties() {
    // Arrange
    INPUT_PROPERTIES.setProperty("kafka.bootstrap.servers", "localhost:9092");
    INPUT_PROPERTIES.setProperty("kafka.client.id", "client-1");
    INPUT_PROPERTIES.setProperty("application.name", "TestApp");
    
    // Act
    Properties kafkaProperties = supplier.get();

    // Assert
    assertThat(kafkaProperties.containsKey("bootstrap.servers")).isTrue();
    assertThat(kafkaProperties.containsKey("client.id")).isTrue();
    assertThat(kafkaProperties.containsKey("application.name")).isFalse();
  }

  @Test
  public void testExtractKafkaProperties_removesKafkaPrefix() {
    // Arrange
    INPUT_PROPERTIES.setProperty("kafka.bootstrap.servers", "localhost:9092");
    INPUT_PROPERTIES.setProperty("kafka.client.id", "client-1");
    INPUT_PROPERTIES.setProperty("application.name", "TestApp");

    // Act
    Properties kafkaProperties = supplier.get();

    // Assert
    assertThat(kafkaProperties.getProperty("bootstrap.servers")).isEqualTo("localhost:9092");
    assertThat(kafkaProperties.getProperty("client.id")).isEqualTo("client-1");
  }

  @Test
  public void testExtractKafkaProperties_emptyInputReturnsEmptyProperties() {
    // Act
    Properties kafkaProperties = supplier.get();

    // Assert
    assertThat(kafkaProperties.isEmpty()).isTrue();
  }

  @Test
  public void testExtractKafkaProperties_noKafkaPropertiesReturnsEmptyProperties() {
    // Arrange
    INPUT_PROPERTIES.setProperty("application.name", "TestApp");

    // Act
    Properties kafkaProperties = supplier.get();

    // Assert
    assertThat(kafkaProperties.isEmpty()).isTrue();
  }
}
