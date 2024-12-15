package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;
import net.sourceforge.argparse4j.inf.Namespace;

import java.util.Properties;
import java.util.function.Supplier;

final class KafkaProperties implements Supplier<Properties> {
  private final Namespace namespace;

  @Inject
  KafkaProperties(Namespace namespace) {
    this.namespace = namespace;
  }

  @Override
  public Properties get() {
    // Create a new Properties object to hold the filtered and modified properties
    Properties kafkaProperties = new Properties();

    // Iterate over the input properties
    namespace.getAttrs().keySet().forEach(key -> {
      // Check if the key starts with the "kafka." prefix
      if (!key.startsWith("kafka.")) continue;

      // Remove the prefix and add the key-value pair to the new Properties object
      String newKey = key.substring("kafka.".length());
      kafkaProperties.setProperty(newKey, namespace.getString(key));
    });

    return kafkaProperties;
  }
}
