package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;
import com.google.mu.util.stream.BiStream;
import net.sourceforge.argparse4j.inf.Namespace;

import java.util.Objects;
import java.util.Properties;
import java.util.Set;
import java.util.function.Supplier;

/**
 * Provides a Properties object containing Kafka producer configurations.
 * 
 * This class filters properties from the given Namespace, extracting all keys starting
 * with "kafka." and removing that prefix. It then ensures that essential Kafka properties
 * are set, applying defaults if necessary.
 */
final class KafkaProperties implements Supplier<Properties> {
  private final Namespace namespace;

  @Inject
  KafkaProperties(Namespace namespace) {
    this.namespace = namespace;
  }

  @Override
  public Properties get() {
    Properties kafkaProperties = new Properties();

    // Iterate over the input properties
    BiStream.from(namespace.getAttrs())
      .filterKeys(key -> key.startsWith("kafka."))
      .mapKeys(key -> key.substring("kafka.".length()))
      .filterValues(Objects::nonNull)
      .mapValues(Object::toString)
      .forEach(kafkaProperties::setProperty);

    // Ensure essential Kafka properties are set
    if (!kafkaProperties.containsKey("bootstrap.servers")) {
      kafkaProperties.setProperty("bootstrap.servers", "localhost:9092");
    }

    // Key serializer default - should be StringSerializer for keys
    if (!kafkaProperties.containsKey("key.serializer")) {
      kafkaProperties.setProperty("key.serializer", "org.apache.kafka.common.serialization.StringSerializer");
    }

    // Value serializer default - must match the data type we're sending (byte[])
    // Ensuring we do not rely on incorrect defaults that cause ClassCastExceptions
    if (!kafkaProperties.containsKey("value.serializer")) {
      kafkaProperties.setProperty("value.serializer", "org.apache.kafka.common.serialization.ByteArraySerializer");
    }

    // If the user didn't specify acks, retries, linger.ms, etc., they remain
    // as defined by defaults from ConfigArguments or the Kafka client defaults.
    // But we at least ensure a sane set of serializers and bootstrap server.

    return kafkaProperties;
  }
}
