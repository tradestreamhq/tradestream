// ExchangeClientUnboundedSourceImpl.kt
package com.verlumen.tradestream.marketdata

import com.google.common.base.Preconditions.checkArgument
import com.google.inject.Inject
import com.google.inject.Provider
import org.apache.beam.sdk.coders.Coder
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.io.UnboundedSource
import org.apache.beam.sdk.options.PipelineOptions
import org.slf4j.LoggerFactory
import java.io.IOException
import java.io.ObjectInputStream
import java.io.Serializable
import java.util.Collections
import javax.annotation.Nullable

/**
 * A concrete implementation of ExchangeClientUnboundedSource configured to read Trade objects.
 * Uses a serializable factory pattern to create readers at runtime.
 */
class ExchangeClientUnboundedSourceImpl @Inject constructor(
    private val readerFactoryProvider: Provider<ExchangeClientUnboundedReader.Factory>
) : ExchangeClientUnboundedSource(), Serializable {
    
    companion object {
        private const val serialVersionUID = 8L
        private val LOG = LoggerFactory.getLogger(ExchangeClientUnboundedSourceImpl::class.java)
    }
    
    // Make the injected factory transient to avoid serialization issues
    @Transient
    private var readerFactory: ExchangeClientUnboundedReader.Factory? = null
    
    /**
     * Implementation of split that returns this source as the only element
     * since WebSocket connections typically cannot be split.
     */
    @Throws(Exception::class)
    override fun split(desiredNumSplits: Int, options: PipelineOptions): List<UnboundedSource<Trade, TradeCheckpointMark>> {
        // No-op implementation returns itself as the only source
        return Collections.singletonList(this)
    }
    
    /**
     * Initializes the reader factory if needed
     */
    private fun ensureReaderFactoryInitialized() {
        if (readerFactory == null) {
            LOG.info("Initializing reader factory from provider")
            readerFactory = readerFactoryProvider.get()
            LOG.info("Reader factory initialized successfully: {}", readerFactory?.javaClass?.name)
        }
    }
    
    /**
     * Implementation of the createReader method that ensures the factory is initialized
     */
    @Throws(IOException::class)
    override fun createReader(options: PipelineOptions, @Nullable checkpointMark: TradeCheckpointMark?): ExchangeClientUnboundedReader {
        LOG.info("Creating ExchangeClientUnboundedReader. Checkpoint: {}", checkpointMark)
        
        // Ensure factory is properly initialized before use
        ensureReaderFactoryInitialized()
        
        if (readerFactory == null) {
            throw IOException("Failed to initialize reader factory")
        }
        
        // Call the factory to create the reader, passing @Assisted parameters
        return readerFactory!!.create(
            this,
            checkpointMark ?: TradeCheckpointMark.INITIAL
        )
    }
    
    /**
     * Returns the Coder for the CheckpointMark object.
     * Required by UnboundedSource.
     */
    override fun getCheckpointMarkCoder(): Coder<TradeCheckpointMark> {
        return SerializableCoder.of(TradeCheckpointMark::class.java)
    }
    
    /**
     * Used for serialization - reinitializes transient fields
     */
    @Throws(IOException::class, ClassNotFoundException::class)
    private fun readObject(inputStream: ObjectInputStream) {
        inputStream.defaultReadObject()
        LOG.info("Deserialized ExchangeClientUnboundedSourceImpl")
        // readerFactory will be null here (it's transient)
        // It will be reinitialized when createReader is called
    }
}
