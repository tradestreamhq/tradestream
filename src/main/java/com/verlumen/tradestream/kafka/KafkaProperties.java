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
    int retries,
    String sslTruststoreLocation,
    String sslTruststorePassword,
    String sslKeystoreLocation,
    String sslKeystorePassword,
    String sslKeyPassword)
    implements Serializable, Supplier<Properties> {

  public static KafkaProperties create(String bootstrapServers) {
    return new KafkaProperties(
        KafkaDefaults.BATCH_SIZE,
        bootstrapServers,
        KafkaDefaults.BUFFER_MEMORY,
        KafkaDefaults.KEY_SERIALIZER,
        KafkaDefaults.VALUE_SERIALIZER,
        KafkaDefaults.SECURITY_PROTOCOL,
        "",
        "",
        KafkaDefaults.ACKS,
        KafkaDefaults.LINGER_MS,
        KafkaDefaults.RETRIES,
        KafkaDefaults.SSL_TRUSTSTORE_LOCATION,
        KafkaDefaults.SSL_TRUSTSTORE_PASSWORD,
        KafkaDefaults.SSL_KEYSTORE_LOCATION,
        KafkaDefaults.SSL_KEYSTORE_PASSWORD,
        KafkaDefaults.SSL_KEY_PASSWORD);
  }

  /**
   * Validates that required SSL configuration is present when using SSL or SASL_SSL protocol.
   *
   * @throws IllegalStateException if SSL is enabled but truststore is not configured
   */
  public void validateSslConfig() {
    if (("SSL".equals(securityProtocol) || "SASL_SSL".equals(securityProtocol))
        && (sslTruststoreLocation == null || sslTruststoreLocation.isEmpty())) {
      throw new IllegalStateException(
          "SSL truststore location must be configured when using "
              + securityProtocol
              + " security protocol. Set KAFKA_SSL_TRUSTSTORE_LOCATION environment variable.");
    }
  }

  @Override
  public Properties get() {
    validateSslConfig();

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

    // SSL/TLS configuration
    if ("SSL".equals(securityProtocol) || "SASL_SSL".equals(securityProtocol)) {
      if (sslTruststoreLocation != null && !sslTruststoreLocation.isEmpty()) {
        kafkaProperties.setProperty("ssl.truststore.location", sslTruststoreLocation);
      }
      if (sslTruststorePassword != null && !sslTruststorePassword.isEmpty()) {
        kafkaProperties.setProperty("ssl.truststore.password", sslTruststorePassword);
      }
      if (sslKeystoreLocation != null && !sslKeystoreLocation.isEmpty()) {
        kafkaProperties.setProperty("ssl.keystore.location", sslKeystoreLocation);
      }
      if (sslKeystorePassword != null && !sslKeystorePassword.isEmpty()) {
        kafkaProperties.setProperty("ssl.keystore.password", sslKeystorePassword);
      }
      if (sslKeyPassword != null && !sslKeyPassword.isEmpty()) {
        kafkaProperties.setProperty("ssl.key.password", sslKeyPassword);
      }
    }

    return kafkaProperties;
  }
}
