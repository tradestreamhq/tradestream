package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;

import java.util.Properties;

final class KafkaProducerPropertiesProvider implements Provider<Properties> {
  private final Properties properties;

  @Inject
  KafkaProducerPropertiesProvider(Properties properties) {
    this.properties = properties;
  }

  @Override
  public Properties get() {
    // Create a new Properties object to hold the filtered and modified properties
    Properties kafkaProperties = new Properties();

    // Iterate over the input properties
    for (String key : properties.stringPropertyNames()) {
      // Check if the key starts with the "kafka." prefix
      if (!key.startsWith("kafka.")) continue;

      // Remove the prefix and add the key-value pair to the new Properties object
      String newKey = key.substring("kafka.".length());
      kafkaProperties.setProperty(newKey, properties.getProperty(key));
    }

    return kafkaProperties;
  }
}
