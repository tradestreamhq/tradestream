package com.verlumen.tradestream.marketdata

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
import org.apache.beam.sdk.transforms.DoFn.ProcessElement
import org.apache.beam.sdk.transforms.DoFn.StateId
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.joda.time.Duration
import org.joda.time.Instant
import java.io.Serializable
import java.util.ArrayList
import com.google.protobuf.util.Timestamps

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

    interface Factory {
        fun create(candleInterval: Duration): TradeToCandle
    }

    override fun expand(input: PCollection<Trade>): PCollection<KV<String, Candle>> {
        logger.atInfo().log("Starting TradeToCandle transform with candle interval: %s", candleInterval)
        return input
            .apply(
                "StatefulCandleProcessing",
                ParDo.of(StatefulTradeProcessor(candleInterval, candleCombineFn))
            )
            .setCoder(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
    }

    private class StatefulTradeProcessor(
        private val candleInterval: Duration,
        private val candleCombineFn: CandleCombineFn
    ) : DoFn<Trade, KV<String, Candle>>(), Serializable {

        companion object {
            private val logger = FluentLogger.forEnclosingClass()
            private const val serialVersionUID = 1L
        }

        @StateId("trades")
        private val tradesSpec: StateSpec<ValueState<ArrayList<Trade>>> =
            StateSpecs.value(SerializableCoder.of(ArrayList::class.java) as Coder<ArrayList<Trade>>)

        @StateId("currentIntervalEnd")
        private val currentIntervalEndSpec: StateSpec<ValueState<Instant>> =
            StateSpecs.value(SerializableCoder.of(Instant::class.java))

        @ProcessElement
        fun processElement(
            context: ProcessContext,
            @StateId("trades") trades: ValueState<ArrayList<Trade>>,
            @StateId("currentIntervalEnd") currentIntervalEnd: ValueState<Instant>
        ) {
            val trade = context.element()
            val currencyPair = trade.currencyPair
            val eventTime = context.timestamp()

            // initialize or retrieve the per-key list of trades
            var tradeList = trades.read() ?: ArrayList<Trade>().also {
                logger.atInfo().log("Created new list for %s", currencyPair)
                val initEnd = calculateIntervalBoundary(eventTime)
                currentIntervalEnd.write(initEnd)
                logger.atInfo().log("Initialized interval-end for %s at %s", currencyPair, initEnd)
            }

            val intervalEnd = currentIntervalEnd.read()!!

            // if we've crossed into a new candle interval, emit and clear the previous interval
            if (eventTime.isAfter(intervalEnd)) {
                emitCandleForPreviousInterval(context, tradeList, intervalEnd)
                // clear the old trades state
                trades.clear()
                // start a fresh list for the new interval
                tradeList = ArrayList()
                val nextEnd = calculateIntervalBoundary(eventTime)
                currentIntervalEnd.write(nextEnd)
                logger.atInfo().log("Updated interval-end for %s to %s", currencyPair, nextEnd)
            }

            // add this trade and write state
            tradeList.add(trade)
            trades.write(tradeList)
            logger.atFine().log("Trade added to %s (size=%d) at %s", currencyPair, tradeList.size, eventTime)
        }

        private fun emitCandleForPreviousInterval(
            context: ProcessContext,
            tradeList: ArrayList<Trade>,
            intervalEnd: Instant
        ) {
            if (tradeList.isEmpty()) return
            val intervalStart = intervalEnd.minus(candleInterval)
            val currencyPair = tradeList.first().currencyPair

            val tradesInWindow = tradeList.filter { t ->
                val ms = t.timestamp.seconds * 1000 + t.timestamp.nanos / 1_000_000
                val ts = Instant(ms)
                ts.isAfter(intervalStart) && !ts.isAfter(intervalEnd)
            }

            if (tradesInWindow.isEmpty()) {
                logger.atInfo().log("No trades in last interval for %s, skipping", currencyPair)
                return
            }

            logger.atInfo().log("Building candle from %d trades for %s", tradesInWindow.size, currencyPair)

            val acc = candleCombineFn.createAccumulator()
            tradesInWindow.forEach { candleCombineFn.addInput(acc, it) }
            val baseCandle = candleCombineFn.extractOutput(acc)

            // build a protobuf Timestamp via util
            val pbTs = Timestamps.fromMillis(intervalEnd.millis)

            // set timestamp and interval
            val finalCandle = baseCandle.toBuilder()
                .setTimestamp(pbTs)
                .setIntervalMillis(candleInterval.millis)
                .build()

            context.outputWithTimestamp(KV.of(currencyPair, finalCandle), intervalEnd)
        }

        private fun calculateIntervalBoundary(ts: Instant): Instant {
            val ms = ts.millis
            val iv = candleInterval.millis
            return Instant(((ms / iv) + 1) * iv)
        }
    }
}
