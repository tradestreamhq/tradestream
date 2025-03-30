package com.verlumen.tradestream.marketdata;

final class ExchangeClientTradeSource extends TradeSource {
  private final ExchangeClientUnboundedSource source;

  @Inject
  ExchangeClientTradeSource(ExchangeClientUnboundedSource source) {
    this.source = source;
  }

  @Override
  public PCollection<Trade> expand(PBegin input) {
    // 1. Read from Kafka.
    PCollection<byte[]> kafkaData = input.apply("ReadFromKafka", kafkaReadTransform);
    // 2. Parse the byte stream into Trade objects.
    return kafkaData.apply("ParseTrades", parseTrades);
  }
}
