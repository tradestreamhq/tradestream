package com.verlumen.tradestream.kafka;

import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.inject.AbstractModule;
import com.google.inject.TypeLiteral;
import org.apache.kafka.clients.producer.KafkaProducer;

public final class KafkaModule extends AbstractModule {
  public static KafkaModule create() {
    return new KafkaModule();
  }
  
  @Override
  protected void configure() {
    bind(new TypeLiteral<KafkaProducer<String, byte[]>>() {})
        .toProvider(KafkaProducerProvider.class);
  }

  private KafkaModule() {}
}
