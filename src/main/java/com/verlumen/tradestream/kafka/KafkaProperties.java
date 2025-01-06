package com.verlumen.tradestream.kafka;

import com.google.common.collect.ImmutableMap;
import com.google.mu.util.stream.BiStream;
import java.util.Properties;
import java.util.function.Supplier;
import java.util.Objects;

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

  @Override
  public Properties get() {
    Properties kafkaProperties = new Properties();
    kafkaProperties.putAll(properties);
    return kafkaProperties;
  }
}
