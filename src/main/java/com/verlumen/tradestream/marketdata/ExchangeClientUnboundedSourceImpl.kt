package com.verlumen.tradestream.marketdata

import com.google.common.base.Preconditions.checkArgument
import com.google.inject.Inject
import com.google.inject.Provider
import com.verlumen.tradestream.instruments.CurrencyPairSupply
import org.apache.beam.sdk.coders.Coder
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.io.UnboundedSource
import org.apache.beam.sdk.options.PipelineOptions
import org.slf4j.LoggerFactory
import java.io.IOException
import java.util.Collections

/**
 * A concrete implementation of ExchangeClientUnboundedSource configured to read Trade objects.
 * Uses an injected factory to create readers which in turn obtain an ExchangeStreamingClient at runtime.
 */
class ExchangeClientUnboundedSourceImpl @Inject constructor(
    private val readerFactory: ExchangeClientUnboundedReader.Factory,
    private val currencyPairSupplyProvider: Provider<CurrencyPairSupply> // Inject Provider instead
) : ExchangeClientUnboundedSource() {
    
    companion object {
        private const val serialVersionUID = 8L
        private val LOG = LoggerFactory.getLogger(ExchangeClientUnboundedSourceImpl::class.java)
    }

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
     * Implementation of the newer createReader method that delegates to our simpler version.
     */
    @Throws(IOException::class)
    override fun createReader(options: PipelineOptions, checkpointMark: TradeCheckpointMark?): ExchangeClientUnboundedReader {
        LOG.info("Creating ExchangeClientUnboundedReader using factory. Checkpoint: {}", checkpointMark)
        // Call the factory to create the reader, passing @Assisted parameters
        return readerFactory.create(
            this,
            // Get CurrencyPairSupply via the injected provider
            currencyPairSupplyProvider.get(),
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
}
