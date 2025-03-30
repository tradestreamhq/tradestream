package com.verlumen.tradestream.marketdata;

import com.google.auto.value.AutoValue;
import org.apache.beam.sdk.transforms.Create;

@AutoValue
abstract class DryRunTradeSource extends TradeSource {
  abstract ImmutableList<Trade> trades();

  DryRunTradeSource
  
  @Override
  public PCollection<Trade> expand(PBegin input) {
   return input.apply(Create.of(trades()));
  }
}
