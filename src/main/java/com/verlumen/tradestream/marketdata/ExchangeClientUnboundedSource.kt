package com.verlumen.tradestream.marketdata

import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.io.UnboundedSource
import org.apache.beam.sdk.options.PipelineOptions
import java.io.IOException
import java.io.Serializable
import javax.annotation.Nullable

/**
 * Abstract base class for exchange client unbounded source that provides trades
 * from streaming exchange APIs.
 *
 * This serves as the base class for implementations that connect to specific exchanges
 * and provide data to Apache Beam pipelines as an unbounded source.
 */
abstract class ExchangeClientUnboundedSource :
    UnboundedSource<Trade, TradeCheckpointMark>(), Serializable {

    companion object {
        private const val serialVersionUID = 7L
    }

    /**
     * Splits this source into multiple sources for parallel processing.
     * Most exchange API implementations will not support true splitting,
     * so default implementation returns a singleton list containing this source.
     */
    @Throws(Exception::class)
    override fun split(desiredNumSplits: Int, options: PipelineOptions): List<UnboundedSource<Trade, TradeCheckpointMark>> {
        // Default implementation: no splitting
        return listOf(this)
    }

    /**
     * Creates a new reader to read from this source with the specified checkpoint.
     * This is the required method signature by the Beam SDK.
     *
     * @param options Pipeline options
     * @param checkpointMark Last checkpoint mark or null if starting fresh
     * @return A new reader for this source
     */
    @Throws(IOException::class)
    abstract override fun createReader(options: PipelineOptions, @Nullable checkpointMark: TradeCheckpointMark?): UnboundedSource.UnboundedReader<Trade>

    /**
     * Gets the expected output coder for Trade objects.
     */
    override fun getOutputCoder() = org.apache.beam.sdk.extensions.protobuf.ProtoCoder.of(Trade::class.java)
}
