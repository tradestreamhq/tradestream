package com.verlumen.tradestream.marketdata

import javax.annotation.Nullable
import java.io.IOException
import org.apache.beam.sdk.coders.Coder
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.io.UnboundedSource
import org.apache.beam.sdk.options.PipelineOptions
import org.slf4j.Logger
import org.slf4j.LoggerFactory

/**
 * An UnboundedSource that reads Trade objects directly from a WebSocket endpoint.
 * Supports checkpointing and deduplication.
 */
class WebSocketTradeUnboundedSource(private val websocketUrl: String) : 
        UnboundedSource<Trade, TradeCheckpointMark>() {

    init {
        require(websocketUrl.isNotBlank()) { "WebSocket URL cannot be null or empty" }
        LOG.info("WebSocketTradeUnboundedSource created for URL: {}", websocketUrl)
    }

    @Throws(Exception::class)
    override fun split(desiredNumSplits: Int, options: PipelineOptions): List<WebSocketTradeUnboundedSource> {
        return listOf(this)
    }

    @Throws(IOException::class)
    override fun createReader(options: PipelineOptions, @Nullable checkpointMark: TradeCheckpointMark?): WebSocketTradeUnboundedReader {
        LOG.info("Creating WebSocketTradeUnboundedReader. Resuming from checkpoint: {}", checkpointMark)
        return WebSocketTradeUnboundedReader(
            this, 
            this.websocketUrl, 
            checkpointMark ?: TradeCheckpointMark.INITIAL
        )
    }

    @Nullable
    override fun getCheckpointMarkCoder(): Coder<TradeCheckpointMark> {
        return SerializableCoder.of(TradeCheckpointMark::class.java)
    }

    override fun getOutputCoder(): Coder<Trade> {
        return ProtoCoder.of(Trade::class.java)
    }

    /**
     * Indicates that the source may produce duplicate records (e.g., if WebSocket or processing restarts)
     * and requires Beam's deduplication mechanism, based on the ID provided by
     * {@link WebSocketTradeUnboundedReader#getCurrentRecordId()}.
     * @return true
     */
    override fun requiresDeduping(): Boolean {
        return true // Enable Beam's deduplication
    }

    fun getWebsocketUrl(): String {
        return websocketUrl
    }

    companion object {
        private val LOG: Logger = LoggerFactory.getLogger(WebSocketTradeUnboundedSource::class.java)
        private const val serialVersionUID = 2L // Incremented version
    }
}
