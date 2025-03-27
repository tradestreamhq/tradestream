package com.verlumen.tradestream.marketdata

import com.google.common.base.Preconditions.checkArgument
import com.verlumen.tradestream.ingestion.CurrencyPairSupply
import com.verlumen.tradestream.ingestion.ExchangeStreamingClient // Still needed for type safety checks etc.
import org.apache.beam.sdk.coders.Coder
import org.apache.beam.sdk.coders.ProtoCoder
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.io.UnboundedSource
import org.apache.beam.sdk.options.PipelineOptions
import org.slf4j.LoggerFactory
import java.io.IOException
import java.io.Serializable
import java.util.Collections
import javax.annotation.Nullable
import javax.inject.Inject

/**
 * An UnboundedSource configured to read Trade objects. Uses an injected factory to create readers
 * which in turn obtain an ExchangeStreamingClient at runtime.
 * This is a no-op implementation.
 */
class ExchangeClientUnboundedSource @Inject constructor(
    private val readerFactory: ExchangeClientUnboundedReader.Factory
) : UnboundedSource<Trade, TradeCheckpointMark>() {

    companion object {
        private const val serialVersionUID = 8L // Incremented version
        private val LOG = LoggerFactory.getLogger(ExchangeClientUnboundedSource::class.java)
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
        // options is a non-null parameter in Kotlin
        LOG.info("Creating ExchangeClientUnboundedReader using factory. Checkpoint: {}", checkpointMark)

        // Call the factory to create the reader, passing @Assisted parameters
        return readerFactory.create(
            this,
            options,
            checkpointMark ?: TradeCheckpointMark.INITIAL
        )
    }

    @Nullable
    override fun getCheckpointMarkCoder(): Coder<TradeCheckpointMark> {
        return SerializableCoder.of(TradeCheckpointMark::class.java)
    }

    override fun getOutputCoder(): Coder<Trade> {
        return ProtoCoder.of(Trade::class.java)
    }

    override fun requiresDeduping(): Boolean {
        return true
    }
}
