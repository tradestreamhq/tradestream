package com.verlumen.tradestream.kafka;

import com.google.inject.Inject;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;

final class TradeSourceImpl extends TradeSource {
  private final KafkaReadTransform<String, byte[]> kafkaReadTransform;
  private final ParseTrades parseTrades;
  private final Pipeline pipeline;

  @Inject
  TradeSourceImpl(
      Pipeline pipeline,
      KafkaReadTransform<String, byte[]> kafkaReadTransform,
      ParseTrades parseTrades) {
    this.pipeline = pipeline;
    this.kafkaReadTransform = kafkaReadTransform;
    this.parseTrades = parseTrades;
  }

  @Override
  public PCollection<Trade> expand(PBegin input) {
    // 1. Read from Kafka.
    PCollection<byte[]> kafkaData = input.apply("ReadFromKafka", kafkaReadTransform);
    // 2. Parse the byte stream into Trade objects.
    return kafkaData.apply("ParseTrades", parseTrades);
  }
}
