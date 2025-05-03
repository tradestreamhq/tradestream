package com.verlumen.tradestream.marketdata

import com.google.common.collect.EvictingQueue
import com.google.common.collect.ImmutableList
import org.apache.beam.sdk.coders.Coder
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.state.StateSpec
import org.apache.beam.sdk.state.StateSpecs
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.values.KV
import org.slf4j.LoggerFactory

/**
 * Buffers the most recent candles per key and emits lookbacks of specified sizes
 * whenever a new candle arrives.
 *
 * Uses Guava's EvictingQueue for efficient fixed-size buffer management.
 */
class CandleLookbackDoFn(
    lookbackSizes: List<Int>
) : DoFn<KV<String, Candle>, KV<String, KV<Int, ImmutableList<Candle>>>>() {

    private val logger = LoggerFactory.getLogger(CandleLookbackDoFn::class.java)
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
        
        logger.info("Initialized CandleLookbackDoFn with lookbackSizes={}, maxQueueSize={}", 
            this.lookbackSizes, this.maxQueueSize)
    }

    companion object {
        fun getCandleQueueCoder(): Coder<EvictingQueue<Candle>> {
            return SerializableCoder.of(EvictingQueue::class.java)
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
            logger.warn("Received null candle value, skipping")
            return
        }
        val key = element.key
        
        logger.debug("Processing candle for key={}, timestamp={}", 
            key, newCandle.timestamp)

        keyState.write(key)
        
        // Get or create queue
        var queue = queueState.read()
        if (queue == null) {
            queue = EvictingQueue.create<Candle>(maxQueueSize)
            logger.info("Created new queue for key={} with maxSize={}", key, maxQueueSize)
        } else {
            logger.debug("Retrieved existing queue for key={}, current size={}/{}", 
                key, queue.size, queue.remainingCapacity() + queue.size)
        }
        
        // Check if we're about to evict elements
        val willEvict = queue.size == queue.remainingCapacity() + queue.size && queue.size > 0
        if (willEvict && logger.isDebugEnabled()) {
            logger.debug("Queue is full, oldest candle will be evicted for key={}", key)
        }
        
        // Add the new candle
        queue.add(newCandle)
        
        // Save updated queue
        queueState.write(queue)
        logger.debug("Updated queue for key={}, new size={}", key, queue.size)
        
        // Process lookbacks immediately
        processLookbacks(context, key, queue)
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
            logger.warn("Attempted to process lookbacks for empty queue, key={}", key)
            return
        }
        
        val queueList = ImmutableList.copyOf(queue)
        val currentSize = queueList.size
        
        logger.debug("Processing lookbacks for key={}, available candles={}, lookback sizes={}", 
            key, currentSize, lookbackSizes)
        
        var emittedCount = 0
        var skippedCount = 0
        
        for (lookbackSize in lookbackSizes) {
            if (lookbackSize > currentSize) {
                logger.debug("Skipping lookback size={} (insufficient data), key={}", 
                    lookbackSize, key)
                skippedCount++
                continue
            }
            
            try {
                val startIndex = currentSize - lookbackSize
                val immutableLookback = queueList.subList(startIndex, currentSize)
                
                context.output(KV.of(key, KV.of(lookbackSize, immutableLookback)))
                emittedCount++
                
                logger.debug("Emitted lookback: key={}, size={}, from={} to={}", 
                    key, lookbackSize, startIndex, currentSize)
            } catch (e: Exception) {
                logger.error("Failed to process lookback: key={}, size={}, error={}", 
                    key, lookbackSize, e.message, e)
            }
        }
        
        logger.info("Lookback processing complete for key={}: emitted={}, skipped={}", 
            key, emittedCount, skippedCount)
    }
}
