package com.verlumen.tradestream.kafka;

import com.google.inject.Inject;
import com.google.inject.Provider;
import com.google.mu.util.stream.BiStream;
import net.sourceforge.argparse4j.inf.Namespace;

import java.util.Properties;
import java.util.function.Supplier;
import java.util.Objects;

public final class KafkaProperties implements Supplier<Properties> {
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
    BiStream.from(namespace.getAttrs())
      .filterKeys(key -> key.startsWith("kafka."))
      .mapKeys(key -> key.substring("kafka.".length()))
      .filterValues(Objects::nonNull)
      .mapValues(Object::toString)
      .forEach(kafkaProperties::setProperty);

    return kafkaProperties;
  }
}
