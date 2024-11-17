package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;

import com.google.inject.Guice;
import com.google.inject.Inject;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

import java.util.Properties;

@RunWith(JUnit4.class)
public class PropertiesProviderTest {
  @Inject private PropertiesProvider provider;

  @Before
  public void setup() {
    Guice.createInjector().injectMembers(this);
  }

  @Test
  public void testPropertiesLoading() throws Exception {
    // Act
    Properties actual = provider.get();

    // Assert
    assertThat(actual).isNotNull();
    assertThat(actual.isEmpty()).isFalse();
    assertThat(actual.getProperty("kafka.bootstrap.servers")).isEqualTo("localhost:9092");
    assertThat(actual.getProperty("kafka.acks")).isEqualTo("all");
    assertThat(actual.getProperty("kafka.retries")).isEqualTo("0");
  }
}
