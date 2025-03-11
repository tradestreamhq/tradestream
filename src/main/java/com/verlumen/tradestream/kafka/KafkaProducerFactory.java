package com.verlumen.tradestream.kafka;

import java.io.Serializable;
import org.apache.kafka.clients.producer.KafkaProducer;

public interface KafkaProducerFactory extends Serializable {
  KafkaProducer<String, byte[]> create();
}
