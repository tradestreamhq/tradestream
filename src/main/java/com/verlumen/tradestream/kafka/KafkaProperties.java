package com.verlumen.tradestream.kafka;

import java.util.Properties;
import java.util.function.Supplier;

public record KafkaProperties(
  String acks,
  int batchSize,
  String bootstrapServers,
  int retries,
  int lingerMs,
  int bufferMemory,
  String keySerializer,
  String valueSerializer,
  String securityProtocol,
  String saslMechanism,
  String saslJaasConfig) implements Supplier<Properties> {

  public static KafkaProperties create(
    String acks,
    int batchSize,
    String bootstrapServers,
    int retries,
    int lingerMs,
    int bufferMemory,
    String keySerializer,
    String valueSerializer) {
    return new KafkaProperties(
      acks, batchSize, bootstrapServers, retries, lingerMs, bufferMemory, keySerializer, valueSerializer, KafkaDefaults.SECURITY_PROTOCOL, "", "");
  }

  @Override
  public Properties get() {
    Properties kafkaProperties = new Properties();
    kafkaProperties.setProperty("acks", acks);
    kafkaProperties.setProperty("batch.size", Integer.toString(batchSize));
    kafkaProperties.setProperty("bootstrap.servers", bootstrapServers);
    kafkaProperties.setProperty("retries", Integer.toString(retries));
    kafkaProperties.setProperty("linger.ms", Integer.toString(lingerMs));
    kafkaProperties.setProperty("buffer.memory", Integer.toString(bufferMemory));
    kafkaProperties.setProperty("key.serializer", keySerializer);
    kafkaProperties.setProperty("value.serializer", valueSerializer);
    kafkaProperties.setProperty("security.protocol", securityProtocol);
    kafkaProperties.setProperty("sasl.mechanism", saslMechanism);
    kafkaProperties.setProperty("sasl.jaas.config", saslJaasConfig);
    return kafkaProperties;
  }
}
