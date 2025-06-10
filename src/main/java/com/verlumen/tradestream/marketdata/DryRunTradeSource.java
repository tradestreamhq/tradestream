package com.verlumen.tradestream.marketdata;

import static com.google.protobuf.util.Timestamps.fromMillis;

import com.google.auto.value.AutoValue;
import com.google.inject.Inject;
import com.google.common.collect.ImmutableList;
import com.google.inject.assistedinject.Assisted;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;


@AutoValue
abstract class DryRunTradeSource extends TradeSource {
  @Inject
  DryRunTradeSource(@Assisted String exchangeName) {
    return new AutoValue_DryRunTradeSource(
        ImmutableList.of(
            Trade.newBuilder()
                .setExchange(exchangeName)
                .setCurrencyPair("DRY/RUN")
                .setTradeId("trade-123")
                .setTimestamp(fromMillis(1259999L))
                .setPrice(50000.0)
                .setVolume(0.1)
                .build()));
  }

  abstract ImmutableList<Trade> trades();

  @Override
  public PCollection<Trade> expand(PBegin input) {
    return input.apply(Create.of(trades()));
  }

  public interface Factory {
    DryRunTradeSource create(String exchangeName);
  }
}
