package com.verlumen.tradestream.kafka;

import com.google.auto.value.AutoValue;
import com.google.common.base.Suppliers;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.TypeLiteral;
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
    bind(KafkaReadTransform.Factory.class).to(KafkaReadTransformFactory.class);
  }

  @Provides
  Supplier<KafkaProducer<String, byte[]>> provideKafkaProducerSupplier(KafkaProducerSupplier supplier) {
    return Suppliers.<KafkaProducer<String, byte[]>>memoize(supplier);
  }
}
