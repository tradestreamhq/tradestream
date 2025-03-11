package com.verlumen.tradestream.kafka;

import com.google.inject.Inject;
import com.google.inject.Provider;
import org.apache.kafka.clients.producer.KafkaProducer;

final class KafkaProducerProvider implements Provider<KafkaProducer<String, byte[]>> {
  private final KafkaProperties properties;

  @Inject
  KafkaProducerProvider(KafkaProperties properties) {
    this.properties = properties;
  }

  @Override
  public KafkaProducer<String, byte[]> get() {
    return new KafkaProducer<>(properties.get());
  }
}
