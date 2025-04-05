package com.verlumen.tradestream.kafka;

import com.google.auto.value.AutoValue;
import com.google.common.base.Suppliers;
import com.google.inject.assistedinject.FactoryModuleBuilder;
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
    bind(KafkaProperties.class).toInstance(KafkaProperties.create(bootstrapServers()));
  }

  @Provides
  Supplier<KafkaProducer<String, byte[]>> provideKafkaProducerSupplier(
      KafkaProducerSupplier supplier) {
    return Suppliers.memoize(new SerializableKafkaProducerSupplier(supplier));
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
