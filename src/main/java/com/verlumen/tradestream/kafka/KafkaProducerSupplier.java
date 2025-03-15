package com.verlumen.tradestream.kafka;

import com.google.inject.Inject;
import java.io.Serializable;
import java.util.function.Supplier;
import org.apache.kafka.clients.producer.KafkaProducer;

final class KafkaProducerSupplier implements Serializable, Supplier<KafkaProducer<String, byte[]>> {
  private final KafkaProperties properties;

  @Inject
  KafkaProducerSupplier(KafkaProperties properties) {
    this.properties = properties;
  }

  @Override
  public KafkaProducer<String, byte[]> get() {
    return new KafkaProducer<>(properties.get());
  }
}
