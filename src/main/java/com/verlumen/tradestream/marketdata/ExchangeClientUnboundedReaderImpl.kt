package com.verlumen.tradestream.marketdata

import com.google.common.base.Preconditions.checkArgument
import com.google.common.base.Preconditions.checkState
import com.google.common.collect.ImmutableList
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.instruments.CurrencyPair
import com.verlumen.tradestream.instruments.CurrencyPairSupply
import org.apache.beam.sdk.io.UnboundedSource
import org.joda.time.Duration
import org.joda.time.Instant
import org.slf4j.LoggerFactory
import java.io.IOException
import java.nio.charset.StandardCharsets
import java.util.concurrent.LinkedBlockingQueue

class ExchangeClientUnboundedReaderImpl @Inject constructor(
    private val exchangeClient: ExchangeStreamingClient,
    private val currencyPairSupply: CurrencyPairSupply,
    @Assisted private val source: ExchangeClientUnboundedSource,
    @Assisted private var currentCheckpointMark: TradeCheckpointMark
) : ExchangeClientUnboundedReader() {

    private val incomingMessagesQueue = LinkedBlockingQueue<Trade>(10000)
    private var clientStreamingActive = false
    private var currentTrade: Trade? = null
    private var currentTradeTimestamp: Instant? = null

    init {
        LOG.info("ExchangeClientUnboundedReader created via factory. Checkpoint: {}", this.currentCheckpointMark)
    }

    override fun start(): Boolean {
        LOG.info("Reader start() called with injected ExchangeStreamingClient: {}", exchangeClient.javaClass.name)

        val pairsToStream: ImmutableList<CurrencyPair>
        try {
            LOG.debug("Calling currencyPairSupply.currencyPairs()...")
            pairsToStream = currencyPairSupply.currencyPairs()
            checkArgument(pairsToStream.isNotEmpty(), "CurrencyPairSupply returned empty list via currencyPairs()")
            LOG.info("Obtained {} currency pairs from CurrencyPairSupply.", pairsToStream.size)
        } catch (e: Exception) {
            LOG.error("Failed to get currency pairs from CurrencyPairSupply", e)
            throw IOException("Failed to get currency pairs from CurrencyPairSupply", e)
        }

        LOG.info("Calling exchangeClient.startStreaming for {} pairs.", pairsToStream.size)
        try {
            exchangeClient.startStreaming(pairsToStream) { trade ->
                trade?.let {
                    try {
                        if (it.hasTimestamp()) {
                            val eventTimestamp = Instant.ofEpochMilli(Timestamps.toMillis(it.getTimestamp()))
                            if (eventTimestamp.isAfter(currentCheckpointMark.lastProcessedTimestamp)) {
                                if (!incomingMessagesQueue.offer(it)) {
                                    LOG.warn("Reader queue full. Dropping trade: {}", it.getTradeId())
                                }
                            } else {
                                LOG.trace("Skipping old trade: ID {}, Timestamp {}", it.getTradeId(), eventTimestamp)
                            }
                        } else {
                            LOG.warn("Trade missing timestamp: {}", it.getTradeId())
                        }
                    } catch (e: Exception) {
                        LOG.error("Error in trade callback: {}", it.getTradeId(), e)
                    }
                }
            }
            clientStreamingActive = true
            LOG.info("exchangeClient.startStreaming called successfully.")
        } catch (e: Exception) {
            clientStreamingActive = false
            LOG.error("Failed to start streaming via ExchangeStreamingClient", e)
            throw IOException("Failed to start ExchangeStreamingClient", e)
        }
        return advance()
    }

    override fun advance(): Boolean {
        checkState(clientStreamingActive || incomingMessagesQueue.isNotEmpty(),
            "Cannot advance: Exchange client streaming not active and queue empty.")

        currentTrade = incomingMessagesQueue.poll()

        return if (currentTrade != null) {
            if (currentTrade!!.hasTimestamp()) {
                currentTradeTimestamp = Instant.ofEpochMilli(Timestamps.toMillis(currentTrade!!.getTimestamp()))
            } else {
                currentTradeTimestamp = Instant.now()
                LOG.warn("Trade {} missing event timestamp, using processing time {}.", 
                    currentTrade!!.getTradeId(), currentTradeTimestamp)
            }
            LOG.debug("Advanced to trade: ID {}, Timestamp: {}", 
                currentTrade!!.getTradeId(), currentTradeTimestamp)
            true
        } else {
            LOG.trace("No message in queue, advance() returns false.")
            // Watermark advancement when idle
            val now = Instant.now()
            if (currentTradeTimestamp == null || now.minus(WATERMARK_IDLE_THRESHOLD).isAfter(currentTradeTimestamp)) {
                currentTradeTimestamp = now
            }
            // Only return true if clientStreamingActive is still true, otherwise false.
            clientStreamingActive
        }
    }

    override fun getCurrentTimestamp(): Instant {
        checkState(currentTradeTimestamp != null, "Timestamp not available. advance() must return true first.")
        return currentTradeTimestamp!!
    }

    override fun getCurrent(): Trade {
        checkState(currentTrade != null, "No current trade available. advance() must return true first.")
        return currentTrade!!
    }

    override fun getCurrentRecordId(): ByteArray {
        checkState(currentTrade != null, "Cannot get record ID: No current trade.")
        val uniqueId = currentTrade!!.getTradeId()
        
        checkArgument(uniqueId.isNotEmpty(),
            "Current trade record is missing a trade_id required for deduplication: %s", currentTrade)
        return uniqueId.toByteArray(StandardCharsets.UTF_8)
    }

    override fun getWatermark(): Instant {
        val lastKnownTimestamp = currentCheckpointMark.lastProcessedTimestamp
        var potentialWatermark = lastKnownTimestamp
        val now = Instant.now()

        // Advance based on processing time only if idle relative to last checkpoint
        if (now.minus(WATERMARK_IDLE_THRESHOLD).isAfter(potentialWatermark)) {
            potentialWatermark = now.minus(WATERMARK_IDLE_THRESHOLD)
            LOG.trace("Advancing watermark due to idle threshold relative to last checkpoint: {}", potentialWatermark)
        }
        LOG.debug("Emitting watermark: {}", potentialWatermark)
        return potentialWatermark
    }

    override fun getCheckpointMark(): TradeCheckpointMark {
        // Checkpoint based on the timestamp of the last successfully *processed* trade
        val checkpointTimestamp = currentTradeTimestamp 
            ?: currentCheckpointMark.lastProcessedTimestamp // Re-use last mark if no new trade advanced

        LOG.debug("Creating checkpoint mark with timestamp: {}", checkpointTimestamp)
        // Update the internal state for the *next* filtering check in the callback
        this.currentCheckpointMark = TradeCheckpointMark(checkpointTimestamp)
        return this.currentCheckpointMark
    }

    override fun getCurrentSource(): UnboundedSource<Trade, *> {
        return source
    }

    override fun close() {
        LOG.info("Closing ExchangeClient reader...")
        clientStreamingActive = false // Signal callback loops to stop processing
        try {
            LOG.info("Calling exchangeClient.stopStreaming()...")
            exchangeClient.stopStreaming()
            LOG.info("exchangeClient.stopStreaming() called successfully.")
        } catch (e: Exception) {
            // Log error but don't prevent rest of close
            LOG.error("Exception during exchangeClient.stopStreaming()", e)
        }

        incomingMessagesQueue.clear()
        LOG.info("ExchangeClient reader closed.")
    }

    companion object {
        private val LOG = LoggerFactory.getLogger(ExchangeClientUnboundedReaderImpl::class.java)
        private val WATERMARK_IDLE_THRESHOLD = Duration.standardSeconds(5)
    }
}
