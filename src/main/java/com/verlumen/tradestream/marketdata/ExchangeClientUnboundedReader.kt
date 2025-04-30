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
import java.io.Serializable
import java.nio.charset.StandardCharsets
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.function.Supplier;

/**
 * An unbounded reader that streams trade data from an exchange.
 *
 * Logging Levels Used:
 * - SEVERE: Critical errors preventing operation.
 * - WARNING: Potential issues, recoverable errors, unexpected data (e.g., missing timestamps, dropped messages).
 * - INFO: Major lifecycle events (start, stop, create), significant configuration (pair count), successful stream connection/disconnection.
 * - FINE: Detailed operational flow, per-message processing, frequent method calls (advance, watermark, checkpoint), queue status. Requires FINE level enabled in logging configuration.
 * - FINER: Very low-level details (e.g., logging full list of currency pairs, handling null trades). Requires FINER level enabled in logging configuration.
 */
class ExchangeClientUnboundedReader(
    private val exchangeClient: ExchangeStreamingClient,
    private val currencyPairSupply: Supplier<List<CurrencyPair>>,
    private val source: ExchangeClientUnboundedSource,
    private var currentCheckpointMark: TradeCheckpointMark
) : UnboundedSource.UnboundedReader<Trade>(), Serializable {

    // Transient to avoid serialization issues with the queue's internal state.
    // Reinitialized in readObject. Need to handle recovery logic if checkpointing.
    @Transient
    private var incomingMessagesQueue = LinkedBlockingQueue<Trade>(10000)

    @Volatile // Ensure visibility across threads if accessed by callback and reader thread
    private var clientStreamingActive = false
    private var currentTrade: Trade? = null
    private var currentTradeTimestamp: Instant? = null

    init {
        // Log creation at INFO, specific checkpoint details at FINE
        logger.atInfo().log("ExchangeClientUnboundedReader created.")
        logger.atFine().log("Initial Checkpoint: %s", this.currentCheckpointMark)
    }

    /**
     * Guice factory for creating ExchangeClientUnboundedReader instances.
     */
    class Factory @Inject constructor(
        private val exchangeClient: ExchangeStreamingClient,
        private val currencyPairSupply: Supplier<List<CurrencyPair>>
    ) : java.io.Serializable {
        /**
         * Creates a new ExchangeClientUnboundedReader instance.
         */
        fun create(
            source: ExchangeClientUnboundedSource,
            mark: TradeCheckpointMark
        ): ExchangeClientUnboundedReader {
            // Creation log handled by the primary constructor's init block
            return ExchangeClientUnboundedReader(
                exchangeClient,
                currencyPairSupply,
                source,
                mark
            )
        }

        // Default serialization is sufficient if members are serializable
        private fun writeObject(out: java.io.ObjectOutputStream) {
            out.defaultWriteObject()
        }

        private fun readObject(input: java.io.ObjectInputStream) {
            input.defaultReadObject()
        }
    }

    /**
     * Starts the reader and begins streaming trade data.
     * @return boolean indicating if the reader successfully advanced to the first element
     */
    @Throws(IOException::class)
    override fun start(): Boolean {
        logger.atInfo().log("Reader start() called.")
        logger.atFine().log("Using ExchangeStreamingClient: %s", exchangeClient.javaClass.name)

        // Get currency pairs to stream
        val pairsToStream = getCurrencyPairs() // Logging is inside this method

        // Start streaming
        startExchangeStreaming(pairsToStream) // Logging is inside this method

        // Try to advance to the first element
        logger.atFine().log("Attempting first advance() call to read initial trade")
        val result = advance() // advance() handles its own logging
        logger.atFine().log("Initial advance() returned: %b", result)
        return result
    }

    /**
     * Gets currency pairs from the supplier.
     * @return list of currency pairs
     */
    @Throws(IOException::class)
    private fun getCurrencyPairs(): List<CurrencyPair> {
        logger.atFine().log("Calling currencyPairSupply.get()...")
        try {
            val pairs = currencyPairSupply.get()
            checkArgument(pairs.isNotEmpty(), "CurrencyPair Supplier returned empty list via currencyPairs()")
            // Log count at INFO, specific pairs at FINER (might be sensitive/verbose)
            logger.atInfo().log("Obtained %d currency pairs from CurrencyPair Supplier.", pairs.size)
            logger.atFiner().log("Currency pairs: %s", pairs)
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
    private fun startExchangeStreaming(pairsToStream: List<CurrencyPair>) {
        logger.atInfo().log("Attempting to start streaming for %d pairs.", pairsToStream.size)
        try {
            exchangeClient.startStreaming(ImmutableList.copyOf(pairsToStream)) { trade ->
                processTrade(trade) // processTrade handles its own logging
            }
            clientStreamingActive = true
            logger.atInfo().log("Exchange client streaming started successfully.")
        } catch (e: Exception) {
            clientStreamingActive = false
            logger.atSevere().withCause(e).log("Failed to start streaming via ExchangeStreamingClient")
            throw IOException("Failed to start ExchangeStreamingClient", e)
        }
    }

    /**
     * Processes a trade from the exchange. Called asynchronously by the exchange client.
     * @param trade the trade to process
     */
    private fun processTrade(trade: Trade?) {
        if (trade == null) {
            // This might happen for keep-alives or end-of-stream signals. Log lightly.
            logger.atFiner().log("Received null trade from exchange client callback.")
            return
        }

        // Check if streaming is still active before processing
        if (!clientStreamingActive) {
            logger.atFine().log("Streaming stopped, ignoring received trade: %s", trade.getTradeId())
            return
        }

        try {
            logger.atFine().log("Received trade: ID %s, Exchange: %s, Pair: %s, Price: %.2f",
                trade.getTradeId(), trade.getExchange(), trade.getCurrencyPair(), trade.getPrice())

            if (!trade.hasTimestamp()) {
                logger.atWarning().log("Trade missing timestamp: %s", trade.getTradeId())
                // Decide whether to skip or assign a processing time timestamp. Skipping for now.
                return
            }

            val eventTimestamp = Instant.ofEpochMilli(Timestamps.toMillis(trade.getTimestamp()))

            // Filter out trades older than the last checkpoint *before* queueing
            if (!eventTimestamp.isAfter(currentCheckpointMark.lastProcessedTimestamp)) {
                logger.atFine().log("Skipping old trade: ID %s, Timestamp %s, Last processed: %s",
                    trade.getTradeId(), eventTimestamp, currentCheckpointMark.lastProcessedTimestamp)
                return
            }

            // Try adding to the queue
            if (!incomingMessagesQueue.offer(trade)) {
                // If the queue is full, log a warning and drop the trade.
                // Consider adding metrics here (e.g., dropped message count).
                logger.atWarning().log("Reader queue full. Dropping trade: %s. Current queue size: %d",
                    trade.getTradeId(), incomingMessagesQueue.size())
            } else {
                logger.atFiner().log("Added trade to queue: %s, Queue size: %d",
                    trade.getTradeId(), incomingMessagesQueue.size())
            }
        } catch (e: Exception) {
            // Log severe error but don't crash the callback thread if possible
            logger.atSevere().withCause(e).log("Error processing trade: %s", trade.getTradeId())
            // Consider adding metrics for processing errors.
        }
    }


    /**
     * Advances the reader to the next trade from the internal queue.
     * @return boolean indicating if there is a current trade after advancing
     */
    @Throws(IOException::class)
    override fun advance(): Boolean {
        logger.atFiner().log("advance() called. Queue size: %d, Streaming active: %b",
             incomingMessagesQueue.size, clientStreamingActive)

        // Check state: We can only advance if streaming is active OR if there are items left in the queue
        // This prevents blocking indefinitely if the stream closed but messages remain.
         checkState(clientStreamingActive || incomingMessagesQueue.isNotEmpty(),
             "Cannot advance: Exchange client streaming not active and queue is empty.")

        // Poll (non-blocking) is appropriate here as Beam calls advance repeatedly.
        // Timeout version could be used if specific wait semantics are needed, but poll() is typical.
        currentTrade = incomingMessagesQueue.poll() // Using poll() instead of take() to avoid blocking Beam thread

        // If no trade is available *right now*, update watermark based on idle time and return false
        if (currentTrade == null) {
             logger.atFiner().log("No message polled from queue, advance() returns false.")
             // Watermark logic moved primarily to getWatermark(), but ensure timestamp exists for it
             if (currentTradeTimestamp == null) {
                 currentTradeTimestamp = currentCheckpointMark.lastProcessedTimestamp // Start from last known good time
             }
             return false
        }

        // Process the retrieved trade
        if (!currentTrade!!.hasTimestamp()) {
            currentTradeTimestamp = Instant.now() // Use processing time as fallback
            logger.atWarning().log("Trade %s missing event timestamp, using processing time %s as current timestamp.",
                 currentTrade!!.getTradeId(), currentTradeTimestamp)
        } else {
            currentTradeTimestamp = Instant.ofEpochMilli(Timestamps.toMillis(currentTrade!!.getTimestamp()))
        }

        // Log advancement details at FINE level
        logger.atFine().log("Advanced to trade: ID %s, Exchange: %s, Pair: %s, Price: %.2f, Timestamp: %s",
            currentTrade!!.getTradeId(),
            currentTrade!!.getExchange(),
            currentTrade!!.getCurrencyPair(),
            currentTrade!!.getPrice(),
            currentTradeTimestamp)
        return true
    }

    /**
     * Gets the timestamp of the current trade.
     * @return the timestamp of the current trade
     */
    override fun getCurrentTimestamp(): Instant {
        checkState(currentTradeTimestamp != null, "Timestamp not available. advance() must return true first, or start() needs initialization.")
        // No logging needed here - called very frequently by Beam framework
        return currentTradeTimestamp!!
    }

    /**
     * Gets the current trade object.
     * @return the current trade
     */
    override fun getCurrent(): Trade {
        checkState(currentTrade != null, "No current trade available. advance() must return true first.")
        // Log at FINER level as this is called for every element processed by Beam
        logger.atFiner().log("getCurrent() returning trade ID: %s", currentTrade!!.getTradeId())
        return currentTrade!!
    }

    /**
     * Gets the unique ID of the current trade for deduplication.
     * @return the byte array representation of the trade ID
     */
    override fun getCurrentRecordId(): ByteArray {
        checkState(currentTrade != null, "Cannot get record ID: No current trade.")
        val uniqueId = currentTrade!!.getTradeId()

        checkArgument(uniqueId.isNotEmpty(),
            "Current trade record is missing a trade_id required for deduplication: %s", currentTrade)
        // No logging needed here - called frequently by Beam framework
        return uniqueId.toByteArray(StandardCharsets.UTF_8)
    }

    /**
     * Gets the current watermark for this reader. Advances based on last processed timestamp
     * or processing time if idle.
     * @return the watermark instant
     */
    override fun getWatermark(): Instant {
        // Watermark is based on the timestamp of the last item *returned* by advance(),
        // or advances with processing time if idle.
        val lastEventTime = currentTradeTimestamp ?: currentCheckpointMark.lastProcessedTimestamp
        var potentialWatermark = lastEventTime

        val now = Instant.now()
        val idleThresholdTime = now.minus(WATERMARK_IDLE_THRESHOLD)

        // If processing time has advanced significantly beyond the last event time,
        // advance the watermark based on processing time to avoid stalling.
        if (idleThresholdTime.isAfter(potentialWatermark)) {
             potentialWatermark = idleThresholdTime
             logger.atFine().log("Advancing watermark due to idle threshold. Watermark set to: %s (now - %s)",
                 potentialWatermark, WATERMARK_IDLE_THRESHOLD)
        } else {
             logger.atFiner().log("Watermark based on last event time: %s", potentialWatermark)
        }

        // Ensure watermark doesn't go backward if processing time was used for a missing timestamp
        if(potentialWatermark.isBefore(currentCheckpointMark.lastProcessedTimestamp)) {
            potentialWatermark = currentCheckpointMark.lastProcessedTimestamp
            logger.atFine().log("Adjusted potential watermark %s to not regress behind last checkpoint %s",
                potentialWatermark, currentCheckpointMark.lastProcessedTimestamp)
        }


        logger.atFine().log("Emitting watermark: %s", potentialWatermark)
        return potentialWatermark
    }


    /**
     * Creates a checkpoint mark representing the current state (timestamp of the last processed trade).
     * @return the trade checkpoint mark
     */
    override fun getCheckpointMark(): TradeCheckpointMark {
        // Checkpoint based on the timestamp of the last trade successfully returned by advance()
        // If advance() hasn't returned true yet, or returned false last time, use the previous checkpoint's timestamp.
        val checkpointTimestamp = currentTradeTimestamp ?: currentCheckpointMark.lastProcessedTimestamp

        logger.atFine().log("Creating checkpoint mark with timestamp: %s", checkpointTimestamp)

        // Update the internal state *after* creating the mark for the framework,
        // ensuring the *next* check in processTrade uses this updated timestamp.
        // This prevents skipping trades that arrive between advance() returning true and getCheckpointMark() being called.
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
     * Closes the reader, stops streaming, and clears the queue.
     */
    @Throws(IOException::class)
    override fun close() {
        logger.atInfo().log("Closing ExchangeClient reader...")
        // Signal the callback thread to stop processing/queueing messages *before* stopping the client
        clientStreamingActive = false

        try {
            logger.atFine().log("Calling exchangeClient.stopStreaming()...")
            exchangeClient.stopStreaming()
            logger.atInfo().log("Exchange client streaming stopped successfully.")
        } catch (e: Exception) {
            // Log error but don't prevent rest of close
            logger.atSevere().withCause(e).log("Exception during exchangeClient.stopStreaming()")
            // Optional: Re-throw as IOException if it's critical that close reflects the failure
            // throw IOException("Failed to cleanly stop ExchangeStreamingClient", e)
        }

        // Clear any remaining messages in the queue
        val remaining = incomingMessagesQueue.size
        if (remaining > 0) {
            logger.atWarning().log("Clearing %d messages from queue during close.", remaining)
            incomingMessagesQueue.clear()
        }

        logger.atInfo().log("ExchangeClient reader closed.")
    }

    // --- Serialization Methods ---

    // Need to handle transient fields during deserialization
    private fun writeObject(out: java.io.ObjectOutputStream) {
        out.defaultWriteObject()
        // No need to write transient fields like the queue explicitly
        logger.atFiner().log("Serializing ExchangeClientUnboundedReader")
    }

    private fun readObject(input: java.io.ObjectInputStream) {
        input.defaultReadObject()
        // Reinitialize transient fields
        incomingMessagesQueue = LinkedBlockingQueue(10000)
        // clientStreamingActive should be false after deserialization; start() will set it.
        // currentTrade and currentTradeTimestamp will be reset by advance().
        logger.atFiner().log("Deserialized ExchangeClientUnboundedReader. Reinitialized queue. Checkpoint: %s", currentCheckpointMark)
        // Note: After deserialization (e.g., pipeline recovery), start() will be called again,
        // which will re-establish the stream based on the persisted checkpointMark.
        // The queue starts empty, and filtering in processTrade ensures only newer messages are added.
    }

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        // How long the reader can be idle (no new messages) before the watermark advances based on processing time.
        private val WATERMARK_IDLE_THRESHOLD = Duration.standardSeconds(10) // Increased slightly

        private const val serialVersionUID = 2L // Increment if fields change significantly
    }
}
