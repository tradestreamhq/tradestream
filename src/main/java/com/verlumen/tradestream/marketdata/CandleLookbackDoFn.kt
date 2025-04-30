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
// Explicit import for Beam Timer
import org.apache.beam.sdk.state.Timer
import org.apache.beam.sdk.transforms.*
import org.apache.beam.sdk.transforms.windowing.BoundedWindow
import org.apache.beam.sdk.values.KV
import org.joda.time.Instant

// Provides a serializable, bounded ArrayDeque suitable for Beam state.
public class SerializableArrayDeque<E : Serializable>(val maxSize: Int) :
    ArrayDeque<E>(maxSize.coerceAtLeast(1)), Serializable {

    companion object {
        private const val serialVersionUID = 1L
        // Coder moved outside companion object for easier access from other classes
    }

    // --- Coder moved outside companion object ---
    // Custom Coder using Beam Coders for elements
    public class SerializableArrayDequeCoder<E : Serializable>(private val elementCoder: Coder<E>) :
        CustomCoder<SerializableArrayDeque<E>>() {

        private val listCoder: Coder<List<E>> = ListCoder.of(elementCoder)
        private val intCoder: Coder<Int> = VarIntCoder.of()

        @Throws(IOException::class)
        override fun encode(value: SerializableArrayDeque<E>, outStream: OutputStream) {
            intCoder.encode(value.maxSize, outStream)
            // Convert to ArrayList for serialization using ListCoder
            listCoder.encode(ArrayList(value), outStream)
        }

        @Throws(IOException::class)
        override fun decode(inStream: InputStream): SerializableArrayDeque<E> {
            val maxSize = intCoder.decode(inStream)
            val list = listCoder.decode(inStream)
            // Reconstruct from the deserialized List
            val deque = SerializableArrayDeque<E>(maxSize)
            deque.addAll(list)
            return deque
        }

        override fun getCoderArguments(): List<Coder<*>> = listOf(elementCoder)

        override fun verifyDeterministic() {
            elementCoder.verifyDeterministic()
        }
    }
    // --- End of Coder ---


    // Enforces maxSize by removing oldest elements first.
    override fun add(element: E): Boolean {
        if (maxSize <= 0) return false
        // Use addLast and pollFirst for standard deque behavior
        while (size >= maxSize) {
            pollFirst() // Remove from the front (oldest)
        }
        super.addLast(element) // Add to the end (newest)
        return true // Return true as per the 'add' contract
    }


    // Basic serialization methods - Using the Custom Coder with Beam is preferred for state.
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
        // Read maxSize but don't reassign if final
        val readMaxSize = ois.readInt()
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
 * Upon timer firing (triggered by the Beam runner based on windowing strategy),
 * this DoFn emits the last `s` candles for each size `s` specified in the `lookbackSizes` list.
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
             // Use the moved coder class directly
            return SerializableArrayDeque.SerializableArrayDequeCoder(ProtoCoder.of(Candle::class.java))
        }
    }

    // State specification for storing the candle queue.
    @StateId("internalCandleQueue")
    private val queueSpec: StateSpec<ValueState<SerializableArrayDeque<Candle>>> =
        StateSpecs.value(getCandleQueueCoder())

    // Timer specification for processing at the end of a window.
    // The timer ID matches the one used in the @OnTimer annotation.
    @TimerId("processWindowTimer")
    private val timerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)


    /**
     * Processes each incoming candle element.
     * Adds the candle to the stateful queue for the corresponding key.
     * Timers are implicitly set by Beam's windowing/triggering mechanism to call @OnTimer.
     */
    @ProcessElement
    fun processElement(
        context: ProcessContext, // Use ProcessContext here
        @StateId("internalCandleQueue") queueState: ValueState<SerializableArrayDeque<Candle>>
        // Timer parameter removed - timer setting is handled by the runner/windowing
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

        // *** Timer setting removed from here ***
        // The @OnTimer method will be called automatically by the Beam runner
        // based on the windowing strategy (e.g., when the watermark passes the end of the window).
    }

    /**
     * Called when the timer fires for a specific key and window.
     * Emits lookback lists for the specified sizes based on the buffered candles.
     */
    @OnTimer("processWindowTimer")
    fun onTimer(
        context: OnTimerContext, // Correct type for @OnTimer
        window: BoundedWindow,   // Access the window the timer fired for
        @StateId("internalCandleQueue") queueState: ValueState<SerializableArrayDeque<Candle>>
    ) {
        // Access key directly from OnTimerContext.
        // If this still causes an "unresolved reference" error, it likely points to
        // a Beam SDK version mismatch or build configuration issue.
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
