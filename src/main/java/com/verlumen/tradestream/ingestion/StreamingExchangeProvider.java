package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;
import info.bitrich.xchangestream.core.StreamingExchange;
import info.bitrich.xchangestream.core.StreamingExchangeFactory;
import net.sourceforge.argparse4j.inf.Namespace;

final class StreamingExchangeProvider implements Provider<StreamingExchange> {
  private final Namespace namespace;

  @Inject
  StreamingExchangeProvider(Namespace namespace) {
    this.namespace = namespace;
  }

  @Override
  public StreamingExchange get() {
    String exchangeName = namesapce.getString("exchangeName");
    return StreamingExchangeFactory.INSTANCE.createExchange(exchangeName);
  }
}
