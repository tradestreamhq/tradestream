package com.verlumen.tradestream.kafka;

import java.io.Serializable;
import java.util.Properties;
import java.util.function.Supplier;

public record KafkaProperties(
    int batchSize,
    String bootstrapServers,
    int bufferMemory,
    String keySerializer,
    String valueSerializer,
    String securityProtocol,
    String saslMechanism,
    String saslJaasConfig,
    String acks,
    int lingerMs,
    int retries)
    implements Serializable, Supplier<Properties> {

  public static KafkaProperties create(String bootstrapServers) {
    return new KafkaProperties(
        KafkaDefaults.BATCH_SIZE,
        bootstrapServers,
        KafkaDefaults.BUFFER_MEMORY,
        KafkaDefaults.KEY_SERIALIZER,
        KafkaDefaults.VALUE_SERIALIZER,
        KafkaDefaults.SECURITY_PROTOCOL,
        KafkaDefaults.SASL_MECHANISM,
        KafkaDefaults.SASL_JAAS_CONFIG,
        KafkaDefaults.ACKS,
        KafkaDefaults.LINGER_MS,
        KafkaDefaults.RETRIES);
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
    if (!saslMechanism.isEmpty()) {
      kafkaProperties.setProperty("sasl.mechanism", saslMechanism);
    }
    if (!saslJaasConfig.isEmpty()) {
      kafkaProperties.setProperty("sasl.jaas.config", saslJaasConfig);
    }
    return kafkaProperties;
  }
}
