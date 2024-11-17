package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingExchangeFactory;

import java.util.Properties;

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
