package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingExchangeFactory;

final class StreamingExchangeProvider implements Provider<StreamingExchange> {
  private final Properties properties;

  @Inject
  StreamingExchangeProvider(Properties properties) {
    this.properties = properties;
  }

  @Override
  public StreamingExchange get() {
    String exchangeName = properties.get("xchange.exchangeName");
    return StreamingExchangeFactory.INSTANCE.createExchange(exchangeName);
  }
}