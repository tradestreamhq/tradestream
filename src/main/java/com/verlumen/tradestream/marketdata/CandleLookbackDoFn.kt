package com.verlumen.tradestream.marketdata

import com.google.common.collect.EvictingQueue
import com.google.common.collect.ImmutableList
import com.google.common.flogger.FluentLogger 
import org.apache.beam.sdk.coders.Coder
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.state.StateSpec
import org.apache.beam.sdk.state.StateSpecs
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.values.KV

/**
 * Buffers the most recent candles per key and emits lookbacks of specified sizes
 * whenever a new candle arrives.
 *
 * Uses Guava's EvictingQueue for efficient fixed-size buffer management.
 */
class CandleLookbackDoFn(
    lookbackSizes: List<Int>
) : DoFn<KV<String, Candle>, KV<String, KV<Int, ImmutableList<Candle>>>>() {
    private val lookbackSizes: List<Int>
    private val maxQueueSize: Int

    init {
        val positiveLookbacks = lookbackSizes.filter { it > 0 }.toSortedSet()
        require(positiveLookbacks.isNotEmpty()) {
            "Lookback sizes list cannot be empty or contain only non-positive values."
        }
        
        this.lookbackSizes = ImmutableList.copyOf(positiveLookbacks)
        val largestLookback = positiveLookbacks.last()
        this.maxQueueSize = (largestLookback * 1.1).toInt().coerceAtLeast(1)
        
        logger.atInfo().log("Initialized CandleLookbackDoFn with lookbackSizes=%s, maxQueueSize=%s", 
            this.lookbackSizes, this.maxQueueSize)
    }

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        fun getCandleQueueCoder(): Coder<EvictingQueue<Candle>> {
            @Suppress("UNCHECKED_CAST")
            return SerializableCoder.of(EvictingQueue::class.java) as Coder<EvictingQueue<Candle>>
        }
    }

    @StateId("candleQueue")
    private val queueSpec: StateSpec<ValueState<EvictingQueue<Candle>>> =
        StateSpecs.value(getCandleQueueCoder())

    @StateId("storedKey")
    private val keySpec: StateSpec<ValueState<String>> = StateSpecs.value(StringUtf8Coder.of())

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @StateId("candleQueue") queueState: ValueState<EvictingQueue<Candle>>,
        @StateId("storedKey") keyState: ValueState<String>
    ) {
        val element = context.element()
        val newCandle = element.value ?: run {
            logger.atWarning().log("Received null candle value, skipping")
            return
        }
        val key = element.key
        
        logger.atFine().log("Processing candle for key=%s, timestamp=%s", 
            key, newCandle.timestamp)

        keyState.write(key)
        
        // Get or create queue
        var queue = queueState.read()
        if (queue == null) {
            queue = EvictingQueue.create<Candle>(maxQueueSize)
            logger.atInfo().log("Created new queue for key=%s with maxSize=%d", key, maxQueueSize)
        } else {
            logger.atFine().log("Retrieved existing queue for key=%s, current size=%d/%d", 
                key, queue.size, queue.remainingCapacity() + queue.size)
        }
        
        // Check if we're about to evict elements
        val willEvict = queue!!.size == queue.remainingCapacity() + queue.size && queue.size > 0
        if (willEvict) {
            logger.atFine().log("Queue is full, oldest candle will be evicted for key=%s", key)
        }
        
        // Add the new candle
        queue!!.add(newCandle)
        
        // Save updated queue
        queueState.write(queue)
        logger.atFine().log("Updated queue for key=%s, new size=%d", key, queue!!.size)
        
        // Process lookbacks immediately
        processLookbacks(context, key, queue!!)
    }
    
    /**
     * Process all lookbacks and emit them to the output.
     */
    private fun processLookbacks(
        context: ProcessContext,
        key: String,
        queue: EvictingQueue<Candle>
    ) {
        if (queue.isEmpty()) {
            logger.atWarning().log("Attempted to process lookbacks for empty queue, key=%s", key)
            return
        }
        
        val queueList = ImmutableList.copyOf(queue)
        val currentSize = queueList.size
        
        // Log queue size at INFO level
        logger.atInfo().log("Processing lookbacks for key=%s, queue size=%d/%d", 
            key, currentSize, queue.remainingCapacity() + queue.size)
        
        var emittedCount = 0
        val skippedSizes = mutableListOf<Int>()
        
        for (lookbackSize in lookbackSizes) {
            if (lookbackSize > currentSize) {
                skippedSizes.add(lookbackSize)
                continue
            }
            
            try {
                val startIndex = currentSize - lookbackSize
                val immutableLookback = queueList.subList(startIndex, currentSize)
                
                context.output(KV.of(key, KV.of(lookbackSize, immutableLookback)))
                emittedCount++
                
                logger.atFine().log("Emitted lookback: key=%s, size=%d, from=%d to=%d", 
                    key, lookbackSize, startIndex, currentSize)
            } catch (e: Exception) {
                logger.atSevere().withCause(e).log(
                    "Failed to process lookback: key=%s, size=%d", key, lookbackSize)
            }
        }
        
        // Log skipped timeframes together at FINE level
        if (skippedSizes.isNotEmpty()) {
            logger.atInfo().log("Skipped lookback sizes for key=%s: %s (insufficient data, queue size=%d)", 
                key, skippedSizes, currentSize)
        }
        
        logger.atInfo().log("Lookback processing complete for key=%s: emitted=%d", 
            key, emittedCount)
    }
}
