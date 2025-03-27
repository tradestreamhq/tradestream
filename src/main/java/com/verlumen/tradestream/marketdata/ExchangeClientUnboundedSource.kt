package com.verlumen.tradestream.marketdata

import org.apache.beam.sdk.coders.Coder
import org.apache.beam.sdk.coders.ProtoCoder
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.io.UnboundedSource
import org.apache.beam.sdk.options.PipelineOptions
import org.slf4j.LoggerFactory
import java.io.IOException
import javax.annotation.Nullable

/**
 * An abstract UnboundedSource configured to read Trade objects.
 * Base class for implementing exchange client unbounded sources.
 */
abstract class ExchangeClientUnboundedSource : UnboundedSource<Trade, TradeCheckpointMark>() {
    companion object {
        private const val serialVersionUID = 8L
        private val LOG = LoggerFactory.getLogger(ExchangeClientUnboundedSource::class.java)
    }

    @Throws(IOException::class)
    abstract override fun createReader(
        options: PipelineOptions, 
        checkpointMark: TradeCheckpointMark?
    ): ExchangeClientUnboundedReader

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
