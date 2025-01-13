package com.verlumen.tradestream.kafka;

import com.google.auto.value.AutoValue;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.inject.AbstractModule;
import com.google.inject.TypeLiteral;
import org.apache.kafka.clients.producer.KafkaProducer;

@AutoValue
public abstract class KafkaModule extends AbstractModule {
  public static KafkaModule create(KafkaProperties kafkaProperties) {
    return new AutoValue_KafkaModule(kafkaProperties);
  }

  abstract KafkaProperties kafkaProperties();
  
  @Override
  protected void configure() {
    bind(KafkaProperties.class).toProvider(this::kafkaProperties);
    bind(new TypeLiteral<KafkaProducer<String, byte[]>>() {})
        .toProvider(KafkaProducerProvider.class);
  }
}
