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
public class SerializableArrayDeque<E : Serializable>(val maxSize: Int) :
    ArrayDeque<E>(maxSize.coerceAtLeast(1)), Serializable {

    companion object {
        private const val serialVersionUID = 1L

        // Custom Coder using Beam Coders for elements
        // Made public as it needs to be accessed from outside the companion object scope
        // within the CandleLookbackDoFn.
        public class SerializableArrayDequeCoder<E : Serializable>(private val elementCoder: Coder<E>) :
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
        // Use addLast and pollFirst for standard deque behavior
        while (size >= maxSize) {
            pollFirst()
        }
        super.addLast(element) // Add to the end
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
        val readMaxSize = ois.readInt() // Read maxSize but don't reassign if final
        val size = ois.readInt()
        // Clear existing elements before adding deserialized ones
        this.clear()
        for (i in 0 until size) {
             @Suppress("UNCHECKED_CAST")
             // Use addLast to maintain order during deserialization
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
        // Filter lookback sizes to be positive and not exceed the internal queue size.
        val positiveLookbacks = lookbackSizes.filter { it > 0 && it <= internalQueueMaxSize }
        // Store as an immutable sorted list to ensure uniqueness and order.
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
             // *** FIX: Qualify the nested class access ***
            return SerializableArrayDeque.SerializableArrayDequeCoder(ProtoCoder.of(Candle::class.java))
        }
    }

    // State specification for storing the candle queue.
    @StateId("internalCandleQueue")
    private val queueSpec: StateSpec<ValueState<SerializableArrayDeque<Candle>>> =
        StateSpecs.value(getCandleQueueCoder())

    // Timer specification for processing at the end of a window.
    @TimerId("processWindowTimer")
    private val timerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)


    /**
     * Processes each incoming candle element.
     * Adds the candle to the stateful queue for the corresponding key.
     * Sets a timer to fire at the end of the window.
     */
    @ProcessElement
    fun processElement(
        context: ProcessContext, // Use ProcessContext here
        @StateId("internalCandleQueue") queueState: ValueState<SerializableArrayDeque<Candle>>,
        @TimerId("processWindowTimer") timer: Timer // Timer parameter
    ) {
        val element = context.element() // Get element from ProcessContext
        val newCandle: Candle = element.value ?: return // Ignore null candles
        val key: String = element.key // Get key from ProcessContext

        // Read the current queue state, initializing if null.
        var queue: SerializableArrayDeque<Candle>? = queueState.read()
        if (queue == null) {
            queue = SerializableArrayDeque(internalQueueMaxSize)
        }

        // Add the new candle to the queue (maintains max size).
        queue.add(newCandle)
        // Write the updated queue back to state.
        queueState.write(queue)

        // Set the timer to fire at the end of the current window.
        // This ensures onTimer is called once per key per window after all elements are processed.
        timer.set(context.window().maxTimestamp())
    }

    /**
     * Called when the timer set in processElement fires (at the end of the window).
     * Emits lookback lists for the specified sizes based on the buffered candles.
     */
    @OnTimer("processWindowTimer")
    fun onTimer(
        context: OnTimerContext, // Correct type for @OnTimer
        window: BoundedWindow,   // Access the window the timer fired for
        @StateId("internalCandleQueue") queueState: ValueState<SerializableArrayDeque<Candle>>
        // No need for the Timer parameter here, as we are *in* the timer callback.
    ) {
        // *** FIX: Access key directly from OnTimerContext ***
        // This assumes the context.key() method exists and works as expected.
        // If this still causes issues, it points to a potential Beam environment/dependency problem.
        val key: String = context.key()
        val queue: SerializableArrayDeque<Candle>? = queueState.read()

        // If the queue is empty or null, nothing to emit.
        if (queue == null || queue.isEmpty()) {
            return
        }

        val currentQueueSize = queue.size
        // Create an immutable snapshot for stable iteration and sublist creation.
        // The queue stores elements oldest to newest internally due to addLast/pollFirst.
        val currentQueueSnapshot = ImmutableList.copyOf(queue) // Oldest to newest

        // Iterate through the requested lookback sizes.
        for (lookbackSize in lookbackSizes) {
            // Check if the current queue has enough elements for this lookback size.
            if (lookbackSize > currentQueueSize) {
                continue // Skip if not enough history
            }

            // Extract the last 'lookbackSize' elements (most recent candles).
            val lookbackElements: ImmutableList<Candle> = try {
                // Sublist from the end of the snapshot.
                currentQueueSnapshot.subList(currentQueueSize - lookbackSize, currentQueueSize)
            } catch (e: IndexOutOfBoundsException) {
                 // Log error and return empty list if sublist fails unexpectedly
                 System.err.println("Error creating sublist: lookbackSize=$lookbackSize, queueSize=$currentQueueSize for key $key. Exception: ${e.message}")
                ImmutableList.of()
            }

            // Only emit if the lookback list is not empty.
            if (lookbackElements.isNotEmpty()) {
                // Emit the result: Key -> <Lookback Size, List of Candles>
                // Timestamp the output with the end of the window for consistency.
                context.outputWithTimestamp(
                    KV.of(key, KV.of(lookbackSize, lookbackElements)),
                    window.maxTimestamp()
                )
            }
        }
        // Optional: Clear the state if it should not persist across windows.
        // queueState.clear()
    }
}
