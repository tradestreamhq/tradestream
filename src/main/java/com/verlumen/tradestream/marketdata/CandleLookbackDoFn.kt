package com.verlumen.tradestream.marketdata

import com.google.common.collect.ImmutableList
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.io.Serializable
import java.util.*
import kotlin.collections.ArrayList
import org.apache.beam.sdk.coders.*
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.state.*
import org.apache.beam.sdk.transforms.*
import org.apache.beam.sdk.transforms.windowing.BoundedWindow
import org.apache.beam.sdk.values.KV
import org.joda.time.Instant

// Provides a serializable, bounded ArrayDeque suitable for Beam state.
public class SerializableArrayDeque<E : Serializable>(val maxSize: Int) : // Changed internal to public
    ArrayDeque<E>(maxSize.coerceAtLeast(1)), Serializable {

    companion object {
        private const val serialVersionUID = 1L

        // Custom Coder using Beam Coders for elements
        public class SerializableArrayDequeCoder<E : Serializable>(private val elementCoder: Coder<E>) : // Changed internal to public
            CustomCoder<SerializableArrayDeque<E>>() {

            private val listCoder: Coder<List<E>> = ListCoder.of(elementCoder)
            private val intCoder: Coder<Int> = VarIntCoder.of()

            @Throws(IOException::class)
            override fun encode(value: SerializableArrayDeque<E>, outStream: OutputStream) {
                intCoder.encode(value.maxSize, outStream)
                listCoder.encode(ArrayList(value), outStream) // Serialize as List
            }

            @Throws(IOException::class)
            override fun decode(inStream: InputStream): SerializableArrayDeque<E> {
                val maxSize = intCoder.decode(inStream)
                val list = listCoder.decode(inStream)
                val deque = SerializableArrayDeque<E>(maxSize)
                deque.addAll(list) // Reconstruct from List
                return deque
            }

            override fun getCoderArguments(): List<Coder<*>> = listOf(elementCoder)

            override fun verifyDeterministic() {
                elementCoder.verifyDeterministic()
            }
        }
    }

    // Enforces maxSize by removing oldest elements first.
    override fun add(element: E): Boolean {
        if (maxSize <= 0) return false
        while (size >= maxSize) {
            pollFirst()
        }
        super.addLast(element) // Call the super method
        return true // Return true as per the 'add' contract
    }


    // Basic serialization methods - Using the Custom Coder with Beam is preferred.
    @Throws(IOException::class)
    private fun writeObject(oos: java.io.ObjectOutputStream) {
        oos.defaultWriteObject()
        oos.writeInt(maxSize)
        oos.writeInt(size)
        for (element in this) { oos.writeObject(element) }
    }

    @Throws(IOException::class, ClassNotFoundException::class)
    private fun readObject(ois: java.io.ObjectInputStream) {
        ois.defaultReadObject()
        // Assumes defaultReadObject handles transient/final fields correctly or they aren't used after construction.
        // Relying on Custom Coder for Beam state is safer.
        val readMaxSize = ois.readInt()
        val size = ois.readInt()
        for (i in 0 until size) {
             @Suppress("UNCHECKED_CAST")
             addLast(ois.readObject() as E)
        }
    }
}

/**
 * Buffers the last N `Candle` elements per key (String) and emits lookbacks.
 *
 * Upon timer firing (triggered by external Beam windowing), this DoFn emits the
 * last `s` candles for each size `s` specified in the `lookbackSizes` list.
 * The internal buffer size (`internalQueueMaxSize`) determines the maximum history retained.
 */
class CandleLookbackDoFn(
    private val internalQueueMaxSize: Int,
    lookbackSizes: List<Int>
) : DoFn<KV<String, Candle>, KV<String, KV<Int, ImmutableList<Candle>>>>() {

    private val lookbackSizes: List<Int> // Stores filtered, sorted, positive lookback sizes

    init {
        val positiveLookbacks = lookbackSizes.filter { it > 0 && it <= internalQueueMaxSize }
        this.lookbackSizes = ImmutableList.copyOf(positiveLookbacks.toSortedSet())
        require(this.lookbackSizes.isNotEmpty()) {
            "Lookback sizes list cannot be empty or contain only values > internalQueueMaxSize or <= 0."
        }
        require(internalQueueMaxSize > 0) { "internalQueueMaxSize must be positive."}
    }

    companion object {
        private const val serialVersionUID = 1L

        // Helper to get the custom coder for the state queue of Candles
        fun getCandleQueueCoder(): Coder<SerializableArrayDeque<Candle>> {
            return SerializableArrayDeque.SerializableArrayDequeCoder(ProtoCoder.of(Candle::class.java))
        }
    }

    @StateId("internalCandleQueue")
    private val queueSpec: StateSpec<ValueState<SerializableArrayDeque<Candle>>> =
        StateSpecs.value(getCandleQueueCoder())

    @TimerId("processWindowTimer")
    private val timerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)


    @ProcessElement
    fun processElement(
        context: ProcessContext, // Use ProcessContext here
        @StateId("internalCandleQueue") queueState: ValueState<SerializableArrayDeque<Candle>>
        // Timer registration is handled by the Beam runner based on windowing
    ) {
        val element = context.element() // Get element from ProcessContext
        val newCandle: Candle = element.value ?: return // Ignore null candles
        val key: String = element.key // Get key from ProcessContext

        var queue: SerializableArrayDeque<Candle>? = queueState.read()
        if (queue == null) {
            queue = SerializableArrayDeque(internalQueueMaxSize)
        }

        queue.add(newCandle) // Adds to end, evicts from front if full
        queueState.write(queue)
    }

    @OnTimer("processWindowTimer")
    fun onTimer(
        context: OnTimerContext, // Correct type for @OnTimer
        window: BoundedWindow,
        @StateId("internalCandleQueue") queueState: ValueState<SerializableArrayDeque<Candle>>
    ) {
        val key: String = context.key() // context.key() should work on OnTimerContext
        val queue: SerializableArrayDeque<Candle>? = queueState.read()

        if (queue == null || queue.isEmpty()) {
            return
        }

        val currentQueueSize = queue.size
        // Create a snapshot for stable iteration
        val currentQueueSnapshot = ArrayList(queue) // Oldest to newest

        for (lookbackSize in lookbackSizes) {
            if (lookbackSize > currentQueueSize) {
                // Cannot fulfill this lookback with current history
                continue
            }

            // Get the last 'lookbackSize' elements (most recent ones)
            val lookbackElements: ImmutableList<Candle> = try {
                ImmutableList.copyOf(
                    currentQueueSnapshot.subList(currentQueueSize - lookbackSize, currentQueueSize)
                )
            } catch (e: IndexOutOfBoundsException) {
                 System.err.println("Error creating sublist: lookbackSize=$lookbackSize, queueSize=$currentQueueSize for key $key")
                ImmutableList.of()
            }

            if (lookbackElements.isNotEmpty()) {
                // Emit: Key -> <Lookback Size, List of Candles>
                context.outputWithTimestamp(
                    KV.of(key, KV.of(lookbackSize, lookbackElements)),
                    window.maxTimestamp() // Timestamp output with window end time
                )
            }
        }
    }
}
