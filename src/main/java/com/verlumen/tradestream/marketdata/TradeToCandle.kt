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
import org.apache.beam.sdk.state.TimerSpec
import org.apache.beam.sdk.state.TimerSpecs
import org.apache.beam.sdk.state.TimeDomain
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.DoFn.OnTimer
import org.apache.beam.sdk.transforms.DoFn.ProcessElement
import org.apache.beam.sdk.transforms.DoFn.StateId
import org.apache.beam.sdk.transforms.DoFn.TimerId
import org.apache.beam.sdk.transforms.MapElements
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.transforms.SerializableFunction
import org.apache.beam.sdk.transforms.windowing.Window
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.TypeDescriptor
import org.apache.beam.sdk.values.TypeDescriptors
import org.joda.time.Duration
import org.joda.time.Instant
import java.io.Serializable
import java.util.ArrayList
import com.google.protobuf.Timestamp as ProtoTimestamp
import com.google.protobuf.util.Timestamps

/**
 * Transforms a stream of trades into OHLCV candles using stateful processing.
 * Emits candles when trades cross interval boundaries or when a timeout gap occurs.
 * Also performs fill-forward: emits last candle on empty intervals.
 */
class TradeToCandle @Inject constructor(
    @Assisted private val candleInterval: Duration,
    private val candleCombineFn: CandleCombineFn
) : PTransform<PCollection<Trade>, PCollection<KV<String, Candle>>>(), Serializable {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val serialVersionUID = 1L
    }

    interface Factory { fun create(candleInterval: Duration): TradeToCandle }

    override fun expand(input: PCollection<Trade>): PCollection<KV<String, Candle>> {
        val keyed = input
            .apply("KeyByPair", MapElements
                .into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptor.of(Trade::class.java)))
                .via(SerializableFunction { t: Trade -> KV.of(t.currencyPair, t) }))
            .setCoder(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Trade::class.java)))

        return keyed
            .apply("StatefulCandle", ParDo.of(StatefulTradeProcessor(candleInterval, candleCombineFn)))
            .setCoder(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle::class.java)))
    }

    private class StatefulTradeProcessor(
        private val candleInterval: Duration,
        private val candleCombineFn: CandleCombineFn
    ) : DoFn<KV<String, Trade>, KV<String, Candle>>(), Serializable {

        companion object { private val logger = FluentLogger.forEnclosingClass(); private const val serialVersionUID = 1L }

        @StateId("trades")
        private val tradesSpec: StateSpec<ValueState<ArrayList<Trade>>> =
            StateSpecs.value(SerializableCoder.of(ArrayList::class.java) as Coder<ArrayList<Trade>>)

        @StateId("currentIntervalEnd")
        private val intervalEndSpec: StateSpec<ValueState<Instant>> =
            StateSpecs.value(SerializableCoder.of(Instant::class.java))

        @StateId("lastCandle")
        private val lastCandleSpec: StateSpec<ValueState<Candle>> =
            StateSpecs.value(ProtoCoder.of(Candle::class.java))

        @TimerId("gapTimer")
        private val gapTimer: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)

        @ProcessElement
        fun processElement(
            context: ProcessContext,
            @StateId("trades") trades: ValueState<ArrayList<Trade>>,
            @StateId("currentIntervalEnd") currentIntervalEnd: ValueState<Instant>,
            @StateId("lastCandle") lastCandleState: ValueState<Candle>
        ) {
            val kv = context.element(); val key = kv.key; val trade = kv.value; val t = context.timestamp()

            // load or init trade list
            var list = trades.read() ?: ArrayList<Trade>().also {
                val initEnd = boundary(t); currentIntervalEnd.write(initEnd)
                context.timer(gapTimer).set(initEnd.plus(candleInterval))
            }
            val end = currentIntervalEnd.read()!!

            if (t.isAfter(end)) {
                // normal boundary: emit
                context.timer(gapTimer).clear()
                emit(context, key, list, end, lastCandleState)
                trades.clear(); list = ArrayList();
                val next = boundary(t); currentIntervalEnd.write(next)
                context.timer(gapTimer).set(next.plus(candleInterval))
            }

            list.add(trade); trades.write(list)
        }

        @OnTimer("gapTimer")
        fun onTimer(
            context: DoFn.OnTimerContext,
            @StateId("trades") trades: ValueState<ArrayList<Trade>>,
            @StateId("currentIntervalEnd") currentIntervalEnd: ValueState<Instant>,
            @StateId("lastCandle") lastCandleState: ValueState<Candle>
        ) {
            val kv = context.element(); val key = kv.key
            val list = trades.read() ?: ArrayList()
            val end = currentIntervalEnd.read()!!
            emit(context, key, list, end, lastCandleState)
            trades.clear();
            val next = end.plus(candleInterval); currentIntervalEnd.write(next)
            context.timer(gapTimer).set(next.plus(candleInterval))
        }

        private fun emit(
            context: Any,
            key: String,
            trades: List<Trade>,
            intervalEnd: Instant,
            lastCandleState: ValueState<Candle>
        ) {
            val candle = if (trades.isNotEmpty()) {
                // build from trades
                val acc = candleCombineFn.createAccumulator()
                trades.forEach { candleCombineFn.addInput(acc, it) }
                candleCombineFn.extractOutput(acc)
            } else {
                // fill-forward using last candle
                lastCandleState.read() ?: return
            }
            // set timestamp & interval
            val ts = Timestamps.fromMillis(intervalEnd.millis)
            val out = candle.toBuilder().setTimestamp(ts).setIntervalMillis(candleInterval.millis).build()
            lastCandleState.write(out)
            when (context) {
                is ProcessContext -> context.outputWithTimestamp(KV.of(key, out), intervalEnd)
                is DoFn.OnTimerContext -> context.outputWithTimestamp(KV.of(key, out), intervalEnd)
            }
        }

        private fun boundary(ts: Instant): Instant {
            val ms = ts.millis; val iv = candleInterval.millis
            return Instant(((ms / iv) + 1) * iv)
        }
    }
}
