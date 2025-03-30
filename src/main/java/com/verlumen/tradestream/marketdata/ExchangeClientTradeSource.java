package com.verlumen.tradestream.marketdata;

import com.google.inject.Inject;
import org.apache.beam.sdk.io.Read;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;

final class ExchangeClientTradeSource extends TradeSource {
  private final ExchangeClientUnboundedSource source;

  @Inject
  ExchangeClientTradeSource(ExchangeClientUnboundedSource source) {
    this.source = source;
  }

  @Override
  public PCollection<Trade> expand(PBegin input) {
    // Read from the exchange using the Unbounded Source.
    // The source directly produces Trade objects.
    return input.apply("ReadFromExchange", Read.from(source));
  }
}
