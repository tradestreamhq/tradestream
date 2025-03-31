package com.verlumen.tradestream.marketdata

import com.google.common.base.Preconditions.checkArgument
import com.google.common.base.Preconditions.checkState
import com.google.common.collect.ImmutableList
import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.instruments.CurrencyPair
import org.apache.beam.sdk.io.UnboundedSource
import org.joda.time.Duration
import org.joda.time.Instant
import java.io.IOException
import java.nio.charset.StandardCharsets
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.function.Supplier;

/**
 * An unbounded reader that streams trade data from an exchange.
 */
class ExchangeClientUnboundedReader(
    private val exchangeClient: ExchangeStreamingClient,
    private val currencyPairSupply: Supplier<ImmutableList<CurrencyPair>>,
    private val source: ExchangeClientUnboundedSource,
    private var currentCheckpointMark: TradeCheckpointMark
) : UnboundedSource.UnboundedReader<Trade>() {

    private val incomingMessagesQueue = LinkedBlockingQueue<Trade>(10000)
    private var clientStreamingActive = false
    private var currentTrade: Trade? = null
    private var currentTradeTimestamp: Instant? = null

    init {
        logger.atInfo().log("ExchangeClientUnboundedReader created. Checkpoint: %s", this.currentCheckpointMark)
    }

    /**
     * Guice factory for creating ExchangeClientUnboundedReader instances.
     */
    class Factory @Inject constructor(
        private val exchangeClient: ExchangeStreamingClient,
        private val currencyPairSupply: Supplier<ImmutableList<CurrencyPair>>
    ) : java.io.Serializable {
        /**
         * Creates a new ExchangeClientUnboundedReader instance.
         */
        fun create(
            source: ExchangeClientUnboundedSource,
            mark: TradeCheckpointMark
        ): ExchangeClientUnboundedReader {
            return ExchangeClientUnboundedReader(
                exchangeClient,
                currencyPairSupply,
                source,
                mark
            )
        }
    }

    /**
     * Starts the reader and begins streaming trade data.
     * @return boolean indicating if the reader successfully advanced to the first element
     */
    @Throws(IOException::class)
    override fun start(): Boolean {
        logger.atInfo().log("Reader start() called with ExchangeStreamingClient: %s", exchangeClient.javaClass.name)

        // Get currency pairs to stream
        val pairsToStream = getCurrencyPairs()
        
        // Start streaming
        startExchangeStreaming(pairsToStream)
        
        // Try to advance to the first element
        return advance()
    }
    
    /**
     * Gets currency pairs from the supplier.
     * @return list of currency pairs
     */
    @Throws(IOException::class)
    private fun getCurrencyPairs(): ImmutableList<CurrencyPair> {
        logger.atFine().log("Calling currencyPairSupply.get()...")
        try {
            val pairs = currencyPairSupply.get()
            checkArgument(pairs.isNotEmpty(), "CurrencyPair Supplier returned empty list via currencyPairs()")
            logger.atInfo().log("Obtained %d currency pairs from CurrencyPair Supplier.", pairs.size)
            return pairs
        } catch (e: Exception) {
            logger.atSevere().withCause(e).log("Failed to get currency pairs from CurrencyPair Supplier")
            throw IOException("Failed to get currency pairs from CurrencyPair Supplier", e)
        }
    }
    
    /**
     * Starts streaming from the exchange.
     * @param pairsToStream list of currency pairs to stream
     */
    @Throws(IOException::class)
    private fun startExchangeStreaming(pairsToStream: ImmutableList<CurrencyPair>) {
        logger.atInfo().log("Calling exchangeClient.startStreaming for %d pairs.", pairsToStream.size)
        try {
            exchangeClient.startStreaming(pairsToStream) { trade ->
                processTrade(trade)
            }
            clientStreamingActive = true
            logger.atInfo().log("exchangeClient.startStreaming called successfully.")
        } catch (e: Exception) {
            clientStreamingActive = false
            logger.atSevere().withCause(e).log("Failed to start streaming via ExchangeStreamingClient")
            throw IOException("Failed to start ExchangeStreamingClient", e)
        }
    }
    
    /**
     * Processes a trade from the exchange.
     * @param trade the trade to process
     */
    private fun processTrade(trade: Trade?) {
        trade ?: return
        
        try {
            if (!trade.hasTimestamp()) {
                logger.atWarning().log("Trade missing timestamp: %s", trade.getTradeId())
                return
            }
            
            val eventTimestamp = Instant.ofEpochMilli(Timestamps.toMillis(trade.getTimestamp()))
            if (!eventTimestamp.isAfter(currentCheckpointMark.lastProcessedTimestamp)) {
                logger.atFiner().log("Skipping old trade: ID %s, Timestamp %s", trade.getTradeId(), eventTimestamp)
                return
            }
            
            if (!incomingMessagesQueue.offer(trade)) {
                logger.atWarning().log("Reader queue full. Dropping trade: %s", trade.getTradeId())
            }
        } catch (e: Exception) {
            logger.atSevere().withCause(e).log("Error processing trade: %s", trade.getTradeId())
        }
    }

    /**
     * Advances the reader to the next trade.
     * @return boolean indicating if there is a current trade after advancing
     */
    @Throws(IOException::class)
    override fun advance(): Boolean {
        checkState(clientStreamingActive || incomingMessagesQueue.isNotEmpty(),
            "Cannot advance: Exchange client streaming not active and queue empty.")

        currentTrade = incomingMessagesQueue.poll()
        
        // If no trade is available, update watermark and return false
        if (currentTrade == null) {
            logger.atFiner().log("No message in queue, advance() returns false.")
            val now = Instant.now()
            if (currentTradeTimestamp == null || now.minus(WATERMARK_IDLE_THRESHOLD).isAfter(currentTradeTimestamp)) {
                currentTradeTimestamp = now
            }
            return false
        }
        
        // Process the retrieved trade
        if (!currentTrade!!.hasTimestamp()) {
            currentTradeTimestamp = Instant.now()
            logger.atWarning().log("Trade %s missing event timestamp, using processing time %s.", 
                currentTrade!!.getTradeId(), currentTradeTimestamp)
        } else {
            currentTradeTimestamp = Instant.ofEpochMilli(Timestamps.toMillis(currentTrade!!.getTimestamp()))
        }
        
        logger.atFine().log("Advanced to trade: ID %s, Timestamp: %s", 
            currentTrade!!.getTradeId(), currentTradeTimestamp)
        return true
    }

    /**
     * Gets the timestamp of the current trade.
     * @return the timestamp of the current trade
     */
    override fun getCurrentTimestamp(): Instant {
        checkState(currentTradeTimestamp != null, "Timestamp not available. advance() must return true first.")
        return currentTradeTimestamp!!
    }

    /**
     * Gets the current trade object.
     * @return the current trade
     */
    override fun getCurrent(): Trade {
        checkState(currentTrade != null, "No current trade available. advance() must return true first.")
        return currentTrade!!
    }

    /**
     * Gets the unique ID of the current trade.
     * @return the byte array representation of the trade ID
     */
    override fun getCurrentRecordId(): ByteArray {
        checkState(currentTrade != null, "Cannot get record ID: No current trade.")
        val uniqueId = currentTrade!!.getTradeId()
        
        checkArgument(uniqueId.isNotEmpty(),
            "Current trade record is missing a trade_id required for deduplication: %s", currentTrade)
        return uniqueId.toByteArray(StandardCharsets.UTF_8)
    }

    /**
     * Gets the current watermark for this reader.
     * @return the watermark instant
     */
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

    /**
     * Gets the checkpoint mark for this reader.
     * @return the trade checkpoint mark
     */
    override fun getCheckpointMark(): TradeCheckpointMark {
        // Checkpoint based on the timestamp of the last successfully *processed* trade
        val checkpointTimestamp = currentTradeTimestamp 
            ?: currentCheckpointMark.lastProcessedTimestamp // Re-use last mark if no new trade advanced

        logger.atFine().log("Creating checkpoint mark with timestamp: %s", checkpointTimestamp)
        // Update the internal state for the *next* filtering check in the callback
        this.currentCheckpointMark = TradeCheckpointMark(checkpointTimestamp)
        return this.currentCheckpointMark
    }

    /**
     * Gets the source that created this reader.
     * @return the unbounded source
     */
    override fun getCurrentSource(): UnboundedSource<Trade, *> {
        return source
    }

    /**
     * Closes the reader and stops streaming.
     */
    @Throws(IOException::class)
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
        
        private const val serialVersionUID = 1L
    }
}
