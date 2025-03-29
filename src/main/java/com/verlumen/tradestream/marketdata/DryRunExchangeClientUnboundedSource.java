package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;
import com.google.protobuf.util.Timestamps;
import java.io.IOException;
import org.apache.beam.sdk.coders.Coder;
import org.apache.beam.sdk.coders.SerializableCoder;
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder;
import org.apache.beam.sdk.io.UnboundedSource;
import org.apache.beam.sdk.options.PipelineOptions;

/**
 * An UnboundedSource that produces a predefined, finite list of Trades for dry runs.
 */
class DryRunExchangeClientUnboundedSource extends ExchangeClientUnboundedSource {
    private static final long serialVersionUID = 1L; // Add serialVersionUID

    // Predefined list of trades for the dry run
    private static final ImmutableList<Trade> PREDEFINED_TRADES = ImmutableList.of(
            Trade.newBuilder()
                    .setExchange("DRY_RUN_EXCHANGE")
                    .setCurrencyPair("BTC/USD")
                    .setTradeId("dry-trade-1")
                    .setTimestamp(Timestamps.fromMillis(1678886400000L)) // Example timestamp 1
                    .setPrice(50000.0)
                    .setVolume(0.1)
                    .build(),
            Trade.newBuilder()
                    .setExchange("DRY_RUN_EXCHANGE")
                    .setCurrencyPair("BTC/USD")
                    .setTradeId("dry-trade-2")
                    .setTimestamp(Timestamps.fromMillis(1678886460000L)) // Example timestamp 2 (1 min later)
                    .setPrice(50100.0)
                    .setVolume(0.05)
                    .build(),
            Trade.newBuilder()
                    .setExchange("DRY_RUN_EXCHANGE")
                    .setCurrencyPair("ETH/USD") // Different currency pair
                    .setTradeId("dry-trade-3")
                    .setTimestamp(Timestamps.fromMillis(1678886520000L)) // Example timestamp 3
                    .setPrice(1600.0)
                    .setVolume(1.2)
                    .build(),
             Trade.newBuilder()
                    .setExchange("DRY_RUN_EXCHANGE")
                    .setCurrencyPair("BTC/USD")
                    .setTradeId("dry-trade-4")
                    .setTimestamp(Timestamps.fromMillis(1678886580000L)) // Example timestamp 4
                    .setPrice(50050.0)
                    .setVolume(0.08)
                    .build()
    );

    private final DryRunExchangeClientUnboundedReader.Factory readerFactory;

    @Inject
    DryRunExchangeClientUnboundedSource(DryRunExchangeClientUnboundedReader.Factory readerFactory) {
            this.readerFactory = readerFactory;
        }

    @Override
    public UnboundedSource.UnboundedReader<Trade> createReader(
            PipelineOptions options, TradeCheckpointMark checkpointMark) throws IOException {
        return readerFactory.create(this, checkpointMark);
    }

    @Override
    public Coder<TradeCheckpointMark> getCheckpointMarkCoder() {
        return SerializableCoder.of(TradeCheckpointMark.class);
    }

    /**
     * Returns the Coder for the output type of this source.
     * Overrides the parent method to specify the correct ProtoCoder for Trade.
     * @return ProtoCoder<Trade>
     */
    @Override
    public ProtoCoder<Trade> getOutputCoder() { // Changed return type to ProtoCoder<Trade>
        return ProtoCoder.of(Trade.class);
    }

    // Method to access the predefined trades, used by the reader
    ImmutableList<Trade> getTrades() {
        return PREDEFINED_TRADES;
    }
}
