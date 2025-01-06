package com.verlumen.tradestream.kafka;

import com.google.common.collect.ImmutableMap;
import com.google.mu.util.stream.BiStream;
import java.util.Map;
import java.util.Objects;
import java.util.Properties;
import java.util.function.Supplier;

public record KafkaProperties(ImmutableMap<String, Object> properties) implements Supplier<Properties> {
  public static KafkaProperties create(Map<String, Object> properties) {
    return new KafkaProperties(
      BiStream.from(properties)
        .filterKeys(key -> key.startsWith("kafka."))
        .mapKeys(key -> key.substring("kafka.".length()))
        .filterValues(Objects::nonNull)
        .mapValues(Object::toString)
        .collect(ImmutableMap::toImmutableMap));
  }

  private KafkaProperties(ImmutableMap<String, Object> properties) {
    this.properties = properties;
  }

  @Override
  public Properties get() {
    Properties kafkaProperties = new Properties();
    kafkaProperties.putAll(properties);
    return kafkaProperties;
  }
}
