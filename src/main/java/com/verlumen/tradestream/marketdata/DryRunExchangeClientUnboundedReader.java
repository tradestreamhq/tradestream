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
class DryRunExchangeClientUnboundedReader extends UnboundedSource.UnboundedReader<Trade> {
    private static final Logger LOG = LoggerFactory.getLogger(DryRunExchangeClientUnboundedReader.class);

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
        LOG.info("DryRunExchangeClientUnboundedReader created. Initial checkpoint: {}", this.currentCheckpointMark);
    }

    @Override
    public boolean start() throws IOException {
        LOG.info("DryRunExchangeClientUnboundedReader starting...");
        // Advance to the first trade *after* the checkpoint timestamp
        currentIndex = 0;
        while (currentIndex < trades.size()) {
            Instant tradeTimestamp = Instant.ofEpochMilli(Timestamps.toMillis(trades.get(currentIndex).getTimestamp()));
            if (tradeTimestamp.isAfter(currentCheckpointMark.getLastProcessedTimestamp())) {
                 LOG.info("Starting at index {} (Timestamp: {}) after checkpoint {}", currentIndex, tradeTimestamp, currentCheckpointMark.getLastProcessedTimestamp());
                 return advance(); // Read the first valid element
            }
            LOG.trace("Skipping trade at index {} (Timestamp: {}) due to checkpoint", currentIndex, tradeTimestamp);
            currentIndex++;
        }
         LOG.info("No trades found after initial checkpoint. Start returns false.");
        return false; // No trades after checkpoint
    }

    @Override
    public boolean advance() throws IOException {
        if (currentIndex >= trades.size()) {
            currentTrade = null;
            currentTradeTimestamp = null; // Keep watermark advancing based on processing time if needed
            LOG.info("Reached end of predefined trades. Advance returns false.");
            return false;
        }

        currentTrade = trades.get(currentIndex);
        currentTradeTimestamp = Instant.ofEpochMilli(Timestamps.toMillis(currentTrade.getTimestamp()));
        LOG.debug("Advanced to trade index {}: ID {}, Timestamp: {}", currentIndex, currentTrade.getTradeId(), currentTradeTimestamp);
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

        LOG.debug("Creating checkpoint mark with timestamp: {}", checkpointTimestamp);
        // Update the internal state for the *next* filtering check in start() if checkpoint is restored
        this.currentCheckpointMark = new TradeCheckpointMark(checkpointTimestamp);
        return this.currentCheckpointMark;
    }


    @Override
    public Instant getWatermark() {
        // For a finite dry run source, the watermark can simply be the timestamp of the last emitted record.
        Instant watermark = currentTradeTimestamp != null ? currentTradeTimestamp : currentCheckpointMark.getLastProcessedTimestamp();
        LOG.debug("Emitting watermark: {}", watermark);
        return watermark;
    }

    @Override
    public UnboundedSource<Trade, ?> getCurrentSource() {
        return source;
    }

    @Override
    public void close() throws IOException {
        LOG.info("Closing DryRunExchangeClientUnboundedReader.");
        // No resources to close
    }
}
