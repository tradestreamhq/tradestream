package com.verlumen.tradestream.kafka;

import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;

/**
 * Now generic on K (key) and V (value).
 */
final class TradeSourceImpl extends TradeSource {
  private final KafkaReadTransform<String, byte[]> kafkaReadTransform;
  private final ParseTrades parseTrades;

  @Inject
  TradeSourceImpl(
      KafkaReadTransform<String, byte[]> kafkaReadTransform,
      ParseTrades parseTrades) {
    this.kafkaReadTransform = kafkaReadTransform;
    this.parseTrades = parseTrades;
  }

  @Override
  public PCollection<Trade> expand() {
    // 1. Read from Kafka.
    PCollection<byte[]> input = pipeline.apply("ReadFromKafka", kafkaReadTransform);

    // 2. Parse the byte stream into Trade objects.
    return input.apply("ParseTrades", parseTrades);
  }
}
