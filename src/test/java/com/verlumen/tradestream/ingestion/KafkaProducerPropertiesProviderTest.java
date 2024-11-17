package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import org.junit.Test;

import java.util.Properties;

@RunWith(JUnit4.class)
public class KafkaProducerPropertiesProviderTest {
  @Bind private static final Properties TEST_PROPERTIES = new Properties();

  @Inject private KafkaProducerPropertiesProvider provider;

  @Before
  public void setup() {
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }

  @After
  public void teardown() {
    TEST_PROPERTIES.clear();
  }

  @Test
  public void testExtractKafkaProperties_containsOnlyKafkaProperties() {
    // Arrange
    TEST_PROPERTIES.setProperty("kafka.bootstrap.servers", "localhost:9092");
    TEST_PROPERTIES.setProperty("kafka.client.id", "client-1");
    TEST_PROPERTIES.setProperty("application.name", "TestApp");
    
    // Act
    Properties kafkaProperties = provider.get();

    // Assert
    assertThat(kafkaProperties.containsKey("bootstrap.servers")).isTrue();
    assertThat(kafkaProperties.containsKey("client.id")).isTrue();
    assertThat(kafkaProperties.containsKey("application.name")).isFalse();
  }

  @Test
  public void testExtractKafkaProperties_removesKafkaPrefix() {
    // Arrange
    TEST_PROPERTIES.setProperty("kafka.bootstrap.servers", "localhost:9092");
    TEST_PROPERTIES.setProperty("kafka.client.id", "client-1");
    TEST_PROPERTIES.setProperty("application.name", "TestApp");

    // Act
    Properties kafkaProperties = provider.get();

    // Assert
    assertThat(kafkaProperties.getProperty("bootstrap.servers")).isEqualTo("localhost:9092");
    assertThat(kafkaProperties.getProperty("client.id")).isEqualTo("client-1");
  }

  @Test
  public void testExtractKafkaProperties_emptyInputReturnsEmptyProperties() {
    // Act
    Properties kafkaProperties = provider.get();

    // Assert
    assertThat(kafkaProperties.isEmpty()).isTrue();
  }

  @Test
  public void testExtractKafkaProperties_noKafkaPropertiesReturnsEmptyProperties() {
    // Arrange
    TEST_PROPERTIES.setProperty("application.name", "TestApp");

    // Act
    Properties kafkaProperties = provider.get();

    // Assert
    assertThat(kafkaProperties.isEmpty()).isTrue();
  }

  @Test
  public void testExtractKafkaProperties_handlesMultipleKafkaProperties() {
    // Arrange
    TEST_PROPERTIES.setProperty("kafka.group.id", "group-1");

    // Act
    Properties kafkaProperties = provider.get();

    // Assert
    assertThat(kafkaProperties.getProperty("group.id")).isEqualTo("group-1");
    assertThat(kafkaProperties.size()).isEqualTo(3);
  }
}
