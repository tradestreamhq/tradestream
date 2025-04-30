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
    }

    // Custom Coder using Beam Coders for elements
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
        val readMaxSize = ois.readInt()
        val size = ois.readInt()
        this.clear() // Clear existing elements before adding deserialized ones
        for (i in 0 until size) {
             @Suppress("UNCHECKED_CAST")
             addLast(ois.readObject() as E) // Use addLast to maintain order
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
        val positiveLookbacks = lookbackSizes.filter { it > 0 && it <= internalQueueMaxSize }
        this.lookbackSizes = ImmutableList.copyOf(positiveLookbacks.toSortedSet())
        require(this.lookbackSizes.isNotEmpty()) {
            "Lookback sizes list cannot be empty or contain only values > internalQueueMaxSize or <= 0."
        }
        require(internalQueueMaxSize > 0) { "internalQueueMaxSize must be positive."}
    }

    companion object {
        private const val serialVersionUID = 1L

        fun getCandleQueueCoder(): Coder<SerializableArrayDeque<Candle>> {
            return SerializableArrayDeque.SerializableArrayDequeCoder(ProtoCoder.of(Candle::class.java))
        }
    }

    @StateId("internalCandleQueue")
    private val queueSpec: StateSpec<ValueState<SerializableArrayDeque<Candle>>> =
        StateSpecs.value(getCandleQueueCoder())

    // *** FIX: Add state to store the key ***
    @StateId("storedKey")
    private val keySpec: StateSpec<ValueState<String>> = StateSpecs.value(StringUtf8Coder.of())

    @TimerId("processWindowTimer")
    private val timerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)


    @ProcessElement
    fun processElement(
        context: ProcessContext,
        window: BoundedWindow,  // Added window parameter here
        @StateId("internalCandleQueue") queueState: ValueState<SerializableArrayDeque<Candle>>,
        @StateId("storedKey") keyState: ValueState<String>,
        @TimerId("processWindowTimer") timer: Timer
    ) {
        val element = context.element()
        val newCandle: Candle = element.value ?: return
        val key: String = element.key

        // Debug existing queue
        val queue = queueState.read() ?: SerializableArrayDeque<Candle>(internalQueueMaxSize)
        System.err.println("DEBUG: Queue before add, key=$key, size=${queue.size}, maxSize=${queue.maxSize}")
        
        // Store the key in state
        keyState.write(key)

        // Add the new candle
        queue.add(newCandle)
        System.err.println("DEBUG: Queue after add, key=$key, size=${queue.size}, maxSize=${queue.maxSize}")
        
        // Save the updated queue
        queueState.write(queue)

        // Set the timer to fire at the end of the current window.
        timer.set(window.maxTimestamp())  // Use window parameter directly
    }

    @OnTimer("processWindowTimer")
    fun onTimer(
        context: OnTimerContext,
        window: BoundedWindow,
        @StateId("internalCandleQueue") queueState: ValueState<SerializableArrayDeque<Candle>>,
        @StateId("storedKey") keyState: ValueState<String>
    ) {
        // Read key from state
        val key: String? = keyState.read()
        val queue: SerializableArrayDeque<Candle>? = queueState.read()

        // If key or queue is missing, we can't proceed.
        if (key == null || queue == null || queue.isEmpty()) {
            // Optionally log a warning if state is unexpectedly missing
            return
        }

        // Convert the queue to a List for easier handling
        val currentQueueSize = queue.size
        val currentQueueItems = ArrayList<Candle>(queue)
        
        // Add debug logs
        System.err.println("DEBUG: Processing timer for key=$key with queueSize=$currentQueueSize, lookbackSizes=${lookbackSizes}")
        
        // Process each requested lookback size
        for (lookbackSize in lookbackSizes) {
            if (lookbackSize > currentQueueSize) {
                System.err.println("DEBUG: Skipping lookbackSize=$lookbackSize as it's larger than queueSize=$currentQueueSize")
                continue
            }
            
            try {
                // Calculate start index for this lookback size
                val startIndex = currentQueueSize - lookbackSize
                
                // Create a separate list for this lookback to ensure proper serialization
                val lookbackElements = ArrayList<Candle>()
                for (i in startIndex until currentQueueSize) {
                    lookbackElements.add(currentQueueItems[i])
                }
                
                // Convert to ImmutableList for output
                val immutableLookback = ImmutableList.copyOf(lookbackElements)
                
                System.err.println("DEBUG: Emitting lookbackSize=$lookbackSize with ${immutableLookback.size} elements")
                
                // Only emit if we have elements
                if (immutableLookback.isNotEmpty()) {
                    context.outputWithTimestamp(
                        KV.of(key, KV.of(lookbackSize, immutableLookback)),
                        window.maxTimestamp()
                    )
                }
            } catch (e: Exception) {
                System.err.println("ERROR: Failed to process lookbackSize=$lookbackSize: ${e.message}")
                e.printStackTrace()
            }
        }
    }
}
