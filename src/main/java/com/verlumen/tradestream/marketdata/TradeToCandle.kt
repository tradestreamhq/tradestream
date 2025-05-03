package com.verlumen.tradestream.marketdata

import com.google.common.collect.EvictingQueue
import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import org.apache.beam.sdk.coders.Coder
import org.apache.beam.sdk.coders.KvCoder
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.state.StateSpec
import org.apache.beam.sdk.state.StateSpecs
import org.apache.beam.sdk.state.TimeDomain
import org.apache.beam.sdk.state.Timer
import org.apache.beam.sdk.state.TimerSpec
import org.apache.beam.sdk.state.TimerSpecs
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.joda.time.Duration
import org.joda.time.Instant
import java.io.Serializable
import com.google.protobuf.Timestamp

/**
 * Transforms a stream of trades into OHLCV candles using stateful processing.
 * This approach maintains state across processing time boundaries but organizes
 * trades into discrete time buckets for proper candle creation.
 */
class TradeToCandle @Inject constructor(
    @Assisted private val candleInterval: Duration,
    private val candleCombineFn: CandleCombineFn
) : PTransform<PCollection<Trade>, PCollection<KV<String, Candle>>>(), Serializable {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val serialVersionUID = 1L
    }

    // Factory interface
    interface Factory {
        fun create(candleInterval: Duration): TradeToCandle
    }

    override fun expand(input: PCollection<Trade>): PCollection<KV<String, Candle>> {
        logger.atInfo().log("Starting TradeToCandle transform with candle interval: %s", candleInterval)

        // Apply stateful transformation
        return input.apply("StatefulCandleProcessing", 
            ParDo.of(StatefulTradeProcessor(candleInterval, candleCombineFn)))
            .setCoder(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
    }

    /**
     * Stateful DoFn that processes trades and emits candles at interval boundaries.
     */
    private class StatefulTradeProcessor(
        private val candleInterval: Duration,
        private val candleCombineFn: CandleCombineFn
    ) : DoFn<Trade, KV<String, Candle>>(), Serializable {
        
        companion object {
            @Transient
            private val logger = FluentLogger.forEnclosingClass()
            private const val serialVersionUID = 1L
            
            // Helper for serializing EvictingQueue containing Trade objects
            fun getTradeQueueCoder(): Coder<EvictingQueue<Trade>> {
                @Suppress("UNCHECKED_CAST")
                return SerializableCoder.of(EvictingQueue::class.java) as Coder<EvictingQueue<Trade>>
            }
        }

        // Maximum trade history to keep per currency pair
        private val maxTradeHistory = 10000

        // State to store trades for each key
        @StateId("tradeBuffer")
        private val tradeBufferSpec = StateSpecs.value(getTradeQueueCoder())
        
        // Timer to emit candles at interval boundaries
        @TimerId("emitTimer")
        private val emitTimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)
        
        // State to track the current interval end time
        @StateId("currentIntervalEnd")
        private val currentIntervalEndSpec = StateSpecs.value(SerializableCoder.of(Instant::class.java))

        @ProcessElement
        fun processElement(
            context: ProcessContext,
            @StateId("tradeBuffer") tradeBuffer: ValueState<EvictingQueue<Trade>>,
            @StateId("currentIntervalEnd") currentIntervalEnd: ValueState<Instant>,
            @TimerId("emitTimer") emitTimer: Timer
        ) {
            val trade = context.element()
            val currencyPair = trade.currencyPair
            val eventTime = context.timestamp()
            
            // Get or create buffer
            var buffer = tradeBuffer.read()
            if (buffer == null) {
                buffer = EvictingQueue.create<Trade>(maxTradeHistory)
                logger.atInfo().log("Created new trade buffer for currency pair: %s", currencyPair)
            }
            
            // Add the trade to the buffer
            buffer.add(trade)
            tradeBuffer.write(buffer)
            
            logger.atFine().log("Added trade to buffer for %s, buffer size: %d, timestamp: %s", 
                currencyPair, buffer.size, eventTime)
            
            // Check if we need to update the timer
            var intervalEnd = currentIntervalEnd.read()
            if (intervalEnd == null || eventTime.isAfter(intervalEnd)) {
                // Calculate the next interval boundary
                intervalEnd = calculateIntervalBoundary(eventTime)
                currentIntervalEnd.write(intervalEnd)
                emitTimer.set(intervalEnd)
                
                logger.atInfo().log("Set timer for %s at interval boundary: %s", 
                    currencyPair, intervalEnd)
            }
        }
        
        @OnTimer("emitTimer")
        fun onTimer(
            context: OnTimerContext,
            @StateId("tradeBuffer") tradeBuffer: ValueState<EvictingQueue<Trade>>,
            @StateId("currentIntervalEnd") currentIntervalEnd: ValueState<Instant>
        ) {
            val intervalEnd = context.timestamp()
            val intervalStart = intervalEnd.minus(candleInterval)
            val buffer = tradeBuffer.read() ?: return
            if (buffer.isEmpty()) return
            
            val currencyPair = buffer.first().currencyPair
            
            logger.atInfo().log("Timer fired for %s at %s, preparing candle for interval %s to %s", 
                currencyPair, intervalEnd, intervalStart, intervalEnd)
            
            // Filter trades that belong to this interval
            val tradesInInterval = buffer.filter { trade -> 
                val tradeTime = Instant(trade.timestamp.seconds * 1000 + trade.timestamp.nanos / 1000000)
                tradeTime.isAfter(intervalStart) && !tradeTime.isAfter(intervalEnd)
            }
            
            if (tradesInInterval.isEmpty()) {
                logger.atInfo().log("No trades found in interval for %s, skipping candle", currencyPair)
                // Set the next timer
                val nextIntervalEnd = calculateIntervalBoundary(intervalEnd.plus(Duration.millis(1)))
                currentIntervalEnd.write(nextIntervalEnd)
                context.timer(nextIntervalEnd).set(nextIntervalEnd)
                return
            }
            
            logger.atInfo().log("Creating candle from %d trades in interval for %s", 
                tradesInInterval.size, currencyPair)
            
            // Use the combiner to create a candle from only the trades in this interval
            val candle = candleCombineFn.createAccumulator()
            
            for (trade in tradesInInterval) {
                candleCombineFn.addInput(candle, trade)
            }
            
            val outputCandle = candleCombineFn.extractOutput(candle)
            
            // Set timestamp on the candle
            val protoTimestamp = Timestamp.newBuilder()
                .setSeconds(intervalEnd.getMillis() / 1000)
                .setNanos(((intervalEnd.getMillis() % 1000) * 1000000).toInt())
                .build()
                
            val timestampedCandle = outputCandle.toBuilder()
                .setTimestamp(protoTimestamp)
                .setInterval(candleInterval.getMillis())
                .build()
            
            // Emit the candle
            context.outputWithTimestamp(KV.of(currencyPair, timestampedCandle), intervalEnd)
            
            // Set the next timer
            val nextIntervalEnd = calculateIntervalBoundary(intervalEnd.plus(Duration.millis(1)))
            currentIntervalEnd.write(nextIntervalEnd)
            context.timer(nextIntervalEnd).set(nextIntervalEnd)
            
            logger.atInfo().log("Set next timer for %s at %s", currencyPair, nextIntervalEnd)
        }
        
        /**
         * Calculate the interval boundary for a given timestamp.
         */
        private fun calculateIntervalBoundary(timestamp: Instant): Instant {
            val millis = timestamp.getMillis()
            val intervalMillis = candleInterval.getMillis()
            val intervalNumber = millis / intervalMillis
            val nextIntervalBoundary = (intervalNumber + 1) * intervalMillis
            return Instant(nextIntervalBoundary)
        }
    }
}
