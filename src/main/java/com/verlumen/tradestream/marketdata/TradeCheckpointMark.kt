package com.verlumen.tradestream.marketdata

import org.apache.beam.sdk.io.UnboundedSource
import org.joda.time.Instant
import java.io.Serializable

/**
 * Checkpoint mark for the WebSocket trade source.
 * Stores the timestamp of the last successfully processed trade.
 * Assumes timestamps are reasonably ordered for watermark/checkpoint purposes.
 */
data class TradeCheckpointMark(
    val lastProcessedTimestamp: Instant = Instant.EPOCH
) : UnboundedSource.CheckpointMark, Serializable {

    companion object {
        private const val serialVersionUID = 1L
        val INITIAL = TradeCheckpointMark(Instant.EPOCH)
    }

    override fun finalizeCheckpoint() {
        // No specific finalization needed for this simple timestamp mark.
    }
}
