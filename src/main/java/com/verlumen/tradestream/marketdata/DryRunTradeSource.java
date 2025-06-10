package com.verlumen.tradestream.marketdata;

import static com.google.protobuf.util.Timestamps.fromMillis;

import com.google.inject.Inject;
import com.google.common.collect.ImmutableList;
import com.google.inject.assistedinject.Assisted;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;

public final class DryRunTradeSource extends TradeSource {
  private final ImmutableList<Trade> trades;

  @Inject
  DryRunTradeSource(@Assisted String exchangeName) {
    this.trades = ImmutableList.of(
        Trade.newBuilder()
            .setExchange(exchangeName)
            .setCurrencyPair("DRY/RUN")
            .setTradeId("trade-123")
            .setTimestamp(fromMillis(1259999L))
            .setPrice(50000.0)
            .setVolume(0.1)
            .build());
  }

  @Override
  public PCollection<Trade> expand(PBegin input) {
    return input.apply(Create.of(trades));
  }

  public interface Factory {
    DryRunTradeSource create(String exchangeName);
  }
}
