package com.verlumen.tradestream.marketdata;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;

@AutoValue
abstract class DryRunTradeSource extends TradeSource {
  static DryRunTradeSource create(ImmutableList<Trade> trades) {
    return new AutoValue_DryRunTradeSource(trades);
  }

  abstract ImmutableList<Trade> trades();

  @Override
  public PCollection<Trade> expand(PBegin input) {
    return input.apply(Create.of(trades()));
  }
}
