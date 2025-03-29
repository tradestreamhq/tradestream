package com.verlumen.tradestream.marketdata
import com.verlumen.tradestream.instruments.CurrencyPair
import org.apache.beam.sdk.io.UnboundedSource
import org.joda.time.Instant
import java.io.IOException

/**
 * Abstract base class for an unbounded reader that streams trade data from an exchange.
 */
abstract class ExchangeClientUnboundedReader : UnboundedSource.UnboundedReader<Trade>() {
    /**
     * Define the factory interface for Guice's FactoryModuleBuilder.
     */
    interface Factory {
        fun create(
            source: ExchangeClientUnboundedSource,
            mark: TradeCheckpointMark
        ): ExchangeClientUnboundedReader
    }
    /**
     * Starts the reader and begins streaming trade data.
     * @return boolean indicating if the reader successfully advanced to the first element
     */
    @Throws(IOException::class)
    abstract override fun start(): Boolean
    
    /**
     * Advances the reader to the next trade.
     * @return boolean indicating if there is a current trade after advancing
     */
    @Throws(IOException::class)
    abstract override fun advance(): Boolean
    
    /**
     * Gets the timestamp of the current trade.
     * @return the timestamp of the current trade
     */
    abstract override fun getCurrentTimestamp(): Instant
    
    /**
     * Gets the current trade object.
     * @return the current trade
     */
    abstract override fun getCurrent(): Trade
    
    /**
     * Gets the unique ID of the current trade.
     * @return the byte array representation of the trade ID
     */
    abstract override fun getCurrentRecordId(): ByteArray
    
    /**
     * Gets the current watermark for this reader.
     * @return the watermark instant
     */
    abstract override fun getWatermark(): Instant
    
    /**
     * Gets the checkpoint mark for this reader.
     * @return the trade checkpoint mark
     */
    abstract override fun getCheckpointMark(): TradeCheckpointMark
    
    /**
     * Gets the source that created this reader.
     * @return the unbounded source
     */
    abstract override fun getCurrentSource(): UnboundedSource<Trade, *>
    
    /**
     * Closes the reader and stops streaming.
     */
    @Throws(IOException::class)
    abstract override fun close()
}
