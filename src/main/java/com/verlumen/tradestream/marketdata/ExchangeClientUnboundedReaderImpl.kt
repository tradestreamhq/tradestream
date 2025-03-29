package com.verlumen.tradestream.marketdata

import com.google.common.base.Preconditions.checkArgument
import com.google.common.base.Preconditions.checkState
import com.google.common.collect.ImmutableList
import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.instruments.CurrencyPair
import com.verlumen.tradestream.instruments.CurrencyPairSupply
import org.apache.beam.sdk.io.UnboundedSource
import org.joda.time.Duration
import org.joda.time.Instant
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
        logger.atInfo().log("ExchangeClientUnboundedReader created via factory. Checkpoint: %s", this.currentCheckpointMark)
    }

    override fun start(): Boolean {
        logger.atInfo().log("Reader start() called with injected ExchangeStreamingClient: %s", exchangeClient.javaClass.name)

        val pairsToStream: ImmutableList<CurrencyPair>
        try {
            logger.atFine().log("Calling currencyPairSupply.currencyPairs()...")
            pairsToStream = currencyPairSupply.currencyPairs()
            checkArgument(pairsToStream.isNotEmpty(), "CurrencyPairSupply returned empty list via currencyPairs()")
            logger.atInfo().log("Obtained %d currency pairs from CurrencyPairSupply.", pairsToStream.size)
        } catch (e: Exception) {
            logger.atSevere().withCause(e).log("Failed to get currency pairs from CurrencyPairSupply")
            throw IOException("Failed to get currency pairs from CurrencyPairSupply", e)
        }

        logger.atInfo().log("Calling exchangeClient.startStreaming for %d pairs.", pairsToStream.size)
        try {
            exchangeClient.startStreaming(pairsToStream) { trade ->
                trade?.let {
                    try {
                        if (it.hasTimestamp()) {
                            val eventTimestamp = Instant.ofEpochMilli(Timestamps.toMillis(it.getTimestamp()))
                            if (eventTimestamp.isAfter(currentCheckpointMark.lastProcessedTimestamp)) {
                                if (!incomingMessagesQueue.offer(it)) {
                                    logger.atWarning().log("Reader queue full. Dropping trade: %s", it.getTradeId())
                                }
                            } else {
                                logger.atFiner().log("Skipping old trade: ID %s, Timestamp %s", it.getTradeId(), eventTimestamp)
                            }
                        } else {
                            logger.atWarning().log("Trade missing timestamp: %s", it.getTradeId())
                        }
                    } catch (e: Exception) {
                        logger.atSevere().withCause(e).log("Error in trade callback: %s", it.getTradeId())
                    }
                }
            }
            clientStreamingActive = true
            logger.atInfo().log("exchangeClient.startStreaming called successfully.")
        } catch (e: Exception) {
            clientStreamingActive = false
            logger.atSevere().withCause(e).log("Failed to start streaming via ExchangeStreamingClient")
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
                logger.atWarning().log("Trade %s missing event timestamp, using processing time %s.", 
                    currentTrade!!.getTradeId(), currentTradeTimestamp)
            }
            logger.atFine().log("Advanced to trade: ID %s, Timestamp: %s", 
                currentTrade!!.getTradeId(), currentTradeTimestamp)
            true
        } else {
            logger.atFiner().log("No message in queue, advance() returns false.")
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
            logger.atFiner().log("Advancing watermark due to idle threshold relative to last checkpoint: %s", potentialWatermark)
        }
        logger.atFine().log("Emitting watermark: %s", potentialWatermark)
        return potentialWatermark
    }

    override fun getCheckpointMark(): TradeCheckpointMark {
        // Checkpoint based on the timestamp of the last successfully *processed* trade
        val checkpointTimestamp = currentTradeTimestamp 
            ?: currentCheckpointMark.lastProcessedTimestamp // Re-use last mark if no new trade advanced

        logger.atFine().log("Creating checkpoint mark with timestamp: %s", checkpointTimestamp)
        // Update the internal state for the *next* filtering check in the callback
        this.currentCheckpointMark = TradeCheckpointMark(checkpointTimestamp)
        return this.currentCheckpointMark
    }

    override fun getCurrentSource(): UnboundedSource<Trade, *> {
        return source
    }

    override fun close() {
        logger.atInfo().log("Closing ExchangeClient reader...")
        clientStreamingActive = false // Signal callback loops to stop processing
        try {
            logger.atInfo().log("Calling exchangeClient.stopStreaming()...")
            exchangeClient.stopStreaming()
            logger.atInfo().log("exchangeClient.stopStreaming() called successfully.")
        } catch (e: Exception) {
            // Log error but don't prevent rest of close
            logger.atSevere().withCause(e).log("Exception during exchangeClient.stopStreaming()")
        }

        incomingMessagesQueue.clear()
        logger.atInfo().log("ExchangeClient reader closed.")
    }

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private val WATERMARK_IDLE_THRESHOLD = Duration.standardSeconds(5)
    }
}
