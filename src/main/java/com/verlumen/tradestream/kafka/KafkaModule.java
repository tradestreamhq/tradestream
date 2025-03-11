package com.verlumen.tradestream.kafka;

import com.google.auto.value.AutoValue;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.inject.AbstractModule;
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
    bind(new TypeLiteral<Supplier<KafkaProducer<String, byte[]>>>() {}).to(KafkaProducerSupplier.class);
    bind(KafkaProperties.class).toInstance(KafkaProperties.create(bootstrapServers()));
    bind(KafkaReadTransform.Factory.class).to(KafkaReadTransformFactory.class);
  }
}
