package com.verlumen.tradestream.marketdata

import com.google.common.base.Preconditions.checkArgument
import com.google.inject.Inject
import com.verlumen.tradestream.ingestion.CurrencyPairSupply
import com.verlumen.tradestream.ingestion.ExchangeStreamingClient
import org.apache.beam.sdk.io.UnboundedSource
import org.apache.beam.sdk.options.PipelineOptions
import org.slf4j.LoggerFactory
import java.io.IOException
import java.util.Collections

/**
 * A concrete implementation of ExchangeClientUnboundedSource configured to read Trade objects.
 * Uses an injected factory to create readers which in turn obtain an ExchangeStreamingClient at runtime.
 * This is a no-op implementation.
 */
class ExchangeClientUnboundedSourceImpl @Inject constructor(
    private val readerFactory: ExchangeClientUnboundedReader.Factory
) : ExchangeClientUnboundedSource() {
    companion object {
        private const val serialVersionUID = 8L
        private val LOG = LoggerFactory.getLogger(ExchangeClientUnboundedSourceImpl::class.java)
    }

    @Throws(Exception::class)
    override fun split(desiredNumSplits: Int, options: PipelineOptions): List<UnboundedSource<Trade, TradeCheckpointMark>> {
        // No-op implementation returns itself as the only source
        return Collections.singletonList(this)
    }

    /**
     * Creates the reader using the injected factory, passing necessary runtime info.
     */
    @Throws(IOException::class)
    override fun createReader(options: PipelineOptions, checkpointMark: TradeCheckpointMark?): ExchangeClientUnboundedReader {
        LOG.info("Creating ExchangeClientUnboundedReader using factory. Checkpoint: {}", checkpointMark)
        // Call the factory to create the reader, passing @Assisted parameters
        return readerFactory.create(
            this,
            options,
            checkpointMark ?: TradeCheckpointMark.INITIAL
        )
    }
}
