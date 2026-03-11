package com.verlumen.tradestream.kafka;

import com.google.auto.value.AutoValue;
import com.google.common.base.Suppliers;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import java.io.Serializable;
import java.util.function.Supplier;
import org.apache.kafka.clients.producer.KafkaProducer;

@AutoValue
public abstract class KafkaModule extends AbstractModule {
  public static KafkaModule create(String bootstrapServers) {
    return new AutoValue_KafkaModule(bootstrapServers);
  }

  abstract String bootstrapServers();

  @Override
  protected void configure() {
    KafkaProperties properties =
        new KafkaProperties(
            KafkaDefaults.BATCH_SIZE,
            bootstrapServers(),
            KafkaDefaults.BUFFER_MEMORY,
            KafkaDefaults.KEY_SERIALIZER,
            KafkaDefaults.VALUE_SERIALIZER,
            envOrDefault("KAFKA_SECURITY_PROTOCOL", KafkaDefaults.SECURITY_PROTOCOL),
            envOrDefault("KAFKA_SASL_MECHANISM", ""),
            envOrDefault("KAFKA_SASL_JAAS_CONFIG", ""),
            KafkaDefaults.ACKS,
            KafkaDefaults.LINGER_MS,
            KafkaDefaults.RETRIES,
            envOrDefault("KAFKA_SSL_TRUSTSTORE_LOCATION", KafkaDefaults.SSL_TRUSTSTORE_LOCATION),
            envOrDefault("KAFKA_SSL_TRUSTSTORE_PASSWORD", KafkaDefaults.SSL_TRUSTSTORE_PASSWORD),
            envOrDefault("KAFKA_SSL_KEYSTORE_LOCATION", KafkaDefaults.SSL_KEYSTORE_LOCATION),
            envOrDefault("KAFKA_SSL_KEYSTORE_PASSWORD", KafkaDefaults.SSL_KEYSTORE_PASSWORD),
            envOrDefault("KAFKA_SSL_KEY_PASSWORD", KafkaDefaults.SSL_KEY_PASSWORD));
    bind(KafkaProperties.class).toInstance(properties);
  }

  @Provides
  Supplier<KafkaProducer<String, byte[]>> provideKafkaProducerSupplier(
      KafkaProducerSupplier supplier) {
    return Suppliers.memoize(new SerializableKafkaProducerSupplier(supplier));
  }

  private static String envOrDefault(String envVar, String defaultValue) {
    String value = System.getenv(envVar);
    return value != null ? value : defaultValue;
  }

  // Static inner class that implements Guava's Supplier and Serializable
  private static class SerializableKafkaProducerSupplier
      implements com.google.common.base.Supplier<KafkaProducer<String, byte[]>>, Serializable {

    private static final long serialVersionUID = 1L;
    private final KafkaProducerSupplier delegate;

    SerializableKafkaProducerSupplier(KafkaProducerSupplier delegate) {
      this.delegate = delegate;
    }

    @Override
    public KafkaProducer<String, byte[]> get() {
      return delegate.get();
    }
  }
}
