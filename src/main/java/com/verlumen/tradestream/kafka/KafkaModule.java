package com.verlumen.tradestream.kafka;

import com.google.auto.value.AutoValue;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.inject.AbstractModule;

@AutoValue
public abstract class KafkaModule extends AbstractModule {
  public static KafkaModule create(String bootstrapServers) {
    return new AutoValue_KafkaModule(bootstrapServers);
  }

  abstract String bootstrapServers();
  
  @Override
  protected void configure() {
    bind(KafkaProducerFactory.class).to(KafkaProducerProviderImpl.class);
    bind(KafkaProperties.class).toInstance(KafkaProperties.create(bootstrapServers()));
    bind(KafkaReadTransform.Factory.class).to(KafkaReadTransformFactory.class);
  }
}
