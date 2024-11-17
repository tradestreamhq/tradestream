package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;
import org.apache.kafka.clients.producer.KafkaProducer;

import java.util.Properties;

final class KafkaProducerProvider implements Provider<KafkaProducer<String, byte[]>> {
  @Inject
  KafkaProducerProvider() {}

  @Override
  public KafkaProducer<String, byte[]> get() {
      Properties props = new Properties();
      props.put("bootstrap.servers", "localhost:9092");
      props.put("acks", "all");
      props.put("retries", 0);
      props.put("batch.size", 16384);
      props.put("linger.ms", 1);
      props.put("buffer.memory", 33554432);
      props.put("key.serializer", "org.apache.kafka.common.serialization.StringSerializer");
      props.put("value.serializer", "org.apache.kafka.common.serialization.StringSerializer");

      return new KafkaProducer<>(props);
  }
}
