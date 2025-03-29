package com.verlumen.tradestream.marketdata;

import static com.google.common.base.Preconditions.checkState;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.util.Timestamps;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.NoSuchElementException;
import org.apache.beam.sdk.io.UnboundedSource;
import org.joda.time.Instant;
import org.slf4j.LoggerFactory;
import org.slf4j.Logger;

/**
 * An UnboundedReader that reads from a predefined, finite list of Trades for dry runs.
 */
class DryRunExchangeClientUnboundedReader extends ExchangeClientUnboundedSource {
    private final DryRunExchangeClientUnboundedSource source;
    private final ImmutableList<Trade> trades;
    private int currentIndex = -1; // Index of the *next* trade to return
    private Trade currentTrade = null;
    private Instant currentTradeTimestamp = null;
    private TradeCheckpointMark currentCheckpointMark;

    DryRunExchangeClientUnboundedReader(DryRunExchangeClientUnboundedSource source, TradeCheckpointMark checkpointMark) {
        this.source = source;
        this.trades = source.getTrades();
        this.currentCheckpointMark = checkpointMark != null ? checkpointMark : TradeCheckpointMark.INITIAL;
    }

    @Override
    public boolean start() throws IOException {
        // Advance to the first trade *after* the checkpoint timestamp
        currentIndex = 0;
        while (currentIndex < trades.size()) {
            Instant tradeTimestamp = Instant.ofEpochMilli(Timestamps.toMillis(trades.get(currentIndex).getTimestamp()));
            if (tradeTimestamp.isAfter(currentCheckpointMark.getLastProcessedTimestamp())) {
                 LOG.info("Starting at index {} (Timestamp: {}) after checkpoint {}", currentIndex, tradeTimestamp, currentCheckpointMark.getLastProcessedTimestamp());
                 return advance(); // Read the first valid element
            }
            currentIndex++;
        }
        return false; // No trades after checkpoint
    }

    @Override
    public boolean advance() throws IOException {
        if (currentIndex >= trades.size()) {
            currentTrade = null;
            currentTradeTimestamp = null; // Keep watermark advancing based on processing time if needed
            return false;
        }

        currentTrade = trades.get(currentIndex);
        currentTradeTimestamp = Instant.ofEpochMilli(Timestamps.toMillis(currentTrade.getTimestamp()));
        currentIndex++;
        return true;
    }

    @Override
    public Instant getCurrentTimestamp() throws NoSuchElementException {
        checkState(currentTradeTimestamp != null, "Timestamp not available. advance() must return true first.");
        return currentTradeTimestamp;
    }

    @Override
    public Trade getCurrent() throws NoSuchElementException {
        checkState(currentTrade != null, "No current trade available. advance() must return true first.");
        return currentTrade;
    }

    @Override
    public byte[] getCurrentRecordId() throws NoSuchElementException {
        checkState(currentTrade != null, "Cannot get record ID: No current trade.");
        return currentTrade.getTradeId().getBytes(StandardCharsets.UTF_8);
    }

    @Override
    public TradeCheckpointMark getCheckpointMark() {
        // Checkpoint based on the timestamp of the last successfully *returned* trade
        Instant checkpointTimestamp = currentTradeTimestamp != null
                ? currentTradeTimestamp
                : currentCheckpointMark.getLastProcessedTimestamp(); // Re-use last mark if no new trade advanced

        // Update the internal state for the *next* filtering check in start() if checkpoint is restored
        this.currentCheckpointMark = new TradeCheckpointMark(checkpointTimestamp);
        return this.currentCheckpointMark;
    }

    @Override
    public Instant getWatermark() {
        // For a finite dry run source, the watermark can simply be the timestamp of the last emitted record.
        Instant watermark = currentTradeTimestamp != null ? currentTradeTimestamp : currentCheckpointMark.getLastProcessedTimestamp();
        return watermark;
    }

    @Override
    public UnboundedSource<Trade, ?> getCurrentSource() {
        return source;
    }

    @Override
    public void close() throws IOException {
        // No resources to close
    }
}
