package com.verlumen.tradestream.marketdata;

import org.apache.beam.sdk.transforms.Create;

final class DryRunTradeSource extends TradeSource {
  private final ImmutableList<Trade> trades;

  @Override
  public PCollection<Trade> expand(PBegin input) {
   return input.apply(Create.of(trades));
  }
}
