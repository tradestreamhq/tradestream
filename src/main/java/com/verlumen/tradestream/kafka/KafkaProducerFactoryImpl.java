package com.verlumen.tradestream.kafka;

import com.google.inject.Inject;
import com.google.inject.Provider;
import org.apache.kafka.clients.producer.KafkaProducer;

final class KafkaProducerFactoryImpl implements KafkaProducerFactory {
  private final KafkaProperties properties;

  @Inject
  KafkaProducerFactoryImpl(KafkaProperties properties) {
    this.properties = properties;
  }

  @Override
  public KafkaProducer<String, byte[]> create() {
    return new KafkaProducer<>(properties.get());
  }
}
