package com.verlumen.tradestream.marketdata

import com.google.common.collect.Lists
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
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.joda.time.Duration
import org.joda.time.Instant
import java.io.Serializable
import java.util.ArrayList
import com.google.protobuf.Timestamp

/**
 * Transforms a stream of trades into OHLCV candles using stateful processing.
 * Emits candles when trades cross interval boundaries.
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
     * Stateful DoFn that processes trades and emits candles when trades cross interval boundaries.
     */
    private class StatefulTradeProcessor(
        private val candleInterval: Duration,
        private val candleCombineFn: CandleCombineFn
    ) : DoFn<Trade, KV<String, Candle>>(), Serializable {
        
        companion object {
            private val logger = FluentLogger.forEnclosingClass()
            private const val serialVersionUID = 1L
        }

        // State to store trades for each key
        @StateId("trades")
        private val tradesSpec = StateSpecs.value(SerializableCoder.of(ArrayList::class.java) as Coder<ArrayList<Trade>>)
        
        // State to track the current interval end time
        @StateId("currentIntervalEnd")
        private val currentIntervalEndSpec = StateSpecs.value(SerializableCoder.of(Instant::class.java))

        @ProcessElement
        fun processElement(
            context: ProcessContext,
            @StateId("trades") trades: ValueState<ArrayList<Trade>>,
            @StateId("currentIntervalEnd") currentIntervalEnd: ValueState<Instant>
        ) {
            val trade = context.element()
            val currencyPair = trade.currencyPair
            val eventTime = context.timestamp()
            
            // Get or create trade list
            var tradeList = trades.read()
            if (tradeList == null) {
                tradeList = ArrayList<Trade>()
                logger.atInfo().log("Created new trade list for currency pair: %s", currencyPair)
                
                // Initialize current interval
                val initialIntervalEnd = calculateIntervalBoundary(eventTime)
                currentIntervalEnd.write(initialIntervalEnd)
                logger.atInfo().log("Initialized first interval end for %s: %s", currencyPair, initialIntervalEnd)
            }
            
            // Check if this trade crosses an interval boundary
            val intervalEnd = currentIntervalEnd.read()
            if (eventTime.isAfter(intervalEnd)) {
                // This trade belongs to a new interval, so emit the candle for the previous one
                emitCandleForPreviousInterval(context, tradeList, intervalEnd)
                
                // Remove trades from the previous interval
                // The current trade is for the new interval, so we'll keep it
                val newTradeList = ArrayList<Trade>()
                
                // Update to the new interval
                val newIntervalEnd = calculateIntervalBoundary(eventTime)
                currentIntervalEnd.write(newIntervalEnd)
                logger.atInfo().log("Updated interval end for %s to %s", currencyPair, newIntervalEnd)
                
                // Clear the trade list by setting it to a new empty list
                tradeList = newTradeList
            }
            
            // Add the trade to the list
            tradeList.add(trade)
            trades.write(tradeList)
            
            logger.atFine().log("Added trade to list for %s, list size: %d, timestamp: %s", 
                currencyPair, tradeList.size, eventTime)
        }
        
        /**
         * Emit a candle for the previous interval.
         */
        private fun emitCandleForPreviousInterval(
            context: ProcessContext,
            tradeList: ArrayList<Trade>,
            intervalEnd: Instant
        ) {
            val intervalStart = intervalEnd.minus(candleInterval)
            
            if (tradeList.isEmpty()) return
            val currencyPair = tradeList.first().currencyPair
            
            // Filter trades that belong to the previous interval
            val tradesInInterval = tradeList.filter { trade -> 
                val tradeTime = Instant(trade.timestamp.seconds * 1000 + trade.timestamp.nanos / 1000000)
                tradeTime.isAfter(intervalStart) && !tradeTime.isAfter(intervalEnd)
            }
            
            if (tradesInInterval.isEmpty()) {
                logger.atInfo().log("No trades found in previous interval for %s, skipping candle", currencyPair)
                return
            }
            
            logger.atInfo().log("Creating candle from %d trades in previous interval for %s", 
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
