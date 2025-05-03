package com.verlumen.tradestream.marketdata

import com.google.common.collect.EvictingQueue
import com.google.common.collect.ImmutableList
import org.apache.beam.sdk.coders.Coder
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.state.StateSpec
import org.apache.beam.sdk.state.StateSpecs
import org.apache.beam.sdk.state.TimeDomain
import org.apache.beam.sdk.state.Timer
import org.apache.beam.sdk.state.TimerSpec
import org.apache.beam.sdk.state.TimerSpecs
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.windowing.BoundedWindow
import org.apache.beam.sdk.values.KV
import org.slf4j.LoggerFactory

/**
 * Buffers the most recent candles per key and emits lookbacks of specified sizes.
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
        
        logger.info("Initialized with lookbackSizes={}, maxQueueSize={}", 
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

    @TimerId("processTimer")
    private val timerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        window: BoundedWindow,
        @StateId("candleQueue") queueState: ValueState<EvictingQueue<Candle>>,
        @StateId("storedKey") keyState: ValueState<String>,
        @TimerId("processTimer") timer: Timer
    ) {
        val element = context.element()
        val newCandle = element.value ?: return
        val key = element.key

        keyState.write(key)
        
        var queue = queueState.read()
        if (queue == null) {
            queue = EvictingQueue.create<Candle>(maxQueueSize)
            logger.debug("Created new queue for key={}", key)
        }
        
        queue.add(newCandle)
        queueState.write(queue)
        timer.set(window.maxTimestamp())
    }

    @OnTimer("processTimer")
    fun onTimer(
        context: OnTimerContext,
        @StateId("candleQueue") queueState: ValueState<EvictingQueue<Candle>>,
        @StateId("storedKey") keyState: ValueState<String>
    ) {
        val key = keyState.read() ?: return
        val queue = queueState.read() ?: return
        
        if (queue.isEmpty()) {
            return
        }
        
        val queueList = ImmutableList.copyOf(queue)
        val currentSize = queueList.size
        
        for (lookbackSize in lookbackSizes) {
            if (lookbackSize > currentSize) {
                continue
            }
            
            try {
                val startIndex = currentSize - lookbackSize
                val immutableLookback = queueList.subList(startIndex, currentSize)
                
                context.output(KV.of(key, KV.of(lookbackSize, immutableLookback)))
            } catch (e: Exception) {
                logger.error("Failed to process lookback: key={}, size={}", 
                    key, lookbackSize, e)
            }
        }
    }
}
