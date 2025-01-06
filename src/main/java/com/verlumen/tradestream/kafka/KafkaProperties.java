package com.verlumen.tradestream.kafka;

import com.google.common.collect.ImmutableMap;
import com.google.inject.Inject;
import com.google.inject.Provider;
import com.google.mu.util.stream.BiStream;
import java.util.Properties;
import java.util.function.Supplier;
import java.util.Objects;
import net.sourceforge.argparse4j.inf.Namespace;

public final class KafkaProperties implements Supplier<Properties> {
  public static KafkaProperties create(ImmutableMap<String, Object> properties) {
    return new KafkaProperties(properties);
  }

  private final ImmutableMap<String, Object> properties;

  @Inject
  KafkaProperties(Namespace namespace) {
    this(ImmutableMap.copyOf(namespace.getAttrs()));
  }

  private KafkaProperties(ImmutableMap<String, Object> properties) {
    this.properties = BiStream.from(properties)
      .filterKeys(key -> key.startsWith("kafka."))
      .mapKeys(key -> key.substring("kafka.".length()))
      .filterValues(Objects::nonNull)
      .mapValues(Object::toString)
      .collect(ImmutableMap::toImmutableMap);
  }

  @Override
  public Properties get() {
    // Create a new Properties object to hold the filtered and modified properties
    Properties kafkaProperties = new Properties();

    // Iterate over the input properties
    BiStream.from(properties)
      .forEach(kafkaProperties::setProperty);

    return kafkaProperties;
  }
}
