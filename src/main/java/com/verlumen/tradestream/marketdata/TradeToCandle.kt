package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import org.apache.beam.sdk.coders.Coder
import org.apache.beam.sdk.coders.KvCoder
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.state.StateId
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
                logger.atInfo().log("Created new trade list for %s", currencyPair)
                val initEnd = calculateIntervalBoundary(eventTime)
                currentIntervalEnd.write(initEnd)
                logger.atInfo().log("Initialized first interval end for %s: %s", currencyPair, initEnd)
            }

            // force non-null Instant
            val intervalEnd = currentIntervalEnd.read()!!

            // if we've crossed into a new candle interval, emit the old one
            if (eventTime.isAfter(intervalEnd)) {
                emitCandleForPreviousInterval(context, tradeList, intervalEnd)
                tradeList = ArrayList()
                val nextEnd = calculateIntervalBoundary(eventTime)
                currentIntervalEnd.write(nextEnd)
                logger.atInfo().log("Updated interval end for %s to %s", currencyPair, nextEnd)
            }

            // always add this trade to the pending list
            tradeList.add(trade)
            trades.write(tradeList)
            logger.atFine().log("Added trade to %s list (size=%d) at %s",
                currencyPair, tradeList.size, eventTime)
        }

        private fun emitCandleForPreviousInterval(
            context: ProcessContext,
            tradeList: ArrayList<Trade>,
            intervalEnd: Instant
        ) {
            if (tradeList.isEmpty()) return
            val intervalStart = intervalEnd.minus(candleInterval)
            val currencyPair = tradeList.first().currencyPair

            // select only the trades in that last interval
            val tradesInWindow = tradeList.filter { t ->
                val tMs = t.timestamp.seconds * 1000 + t.timestamp.nanos / 1_000_000
                val ts = Instant(tMs)
                ts.isAfter(intervalStart) && !ts.isAfter(intervalEnd)
            }

            if (tradesInWindow.isEmpty()) {
                logger.atInfo().log("No trades in last interval for %s, skipping", currencyPair)
                return
            }

            logger.atInfo().log("Building candle from %d trades for %s",
                tradesInWindow.size, currencyPair)

            // combine them into a candle
            val acc = candleCombineFn.createAccumulator()
            tradesInWindow.forEach { candleCombineFn.addInput(acc, it) }
            val baseCandle = candleCombineFn.extractOutput(acc)

            // build a proper protobuf Timestamp
            val pbTs = Timestamp
                .getDefaultInstance()
                .toBuilder()
                .setSeconds(intervalEnd.millis / 1000)
                .setNanos(((intervalEnd.millis % 1000) * 1_000_000).toInt())
                .build()

            // and set it, plus the interval length
            val finalCandle = baseCandle
                .toBuilder()
                .setTimestamp(pbTs)
                .setIntervalMillis(candleInterval.millis)
                .build()

            context.outputWithTimestamp(KV.of(currencyPair, finalCandle), intervalEnd)
        }

        private fun calculateIntervalBoundary(ts: Instant): Instant {
            val ms = ts.millis
            val iv = candleInterval.millis
            val boundary = (ms / iv + 1) * iv
            return Instant(boundary)
        }
    }
}
