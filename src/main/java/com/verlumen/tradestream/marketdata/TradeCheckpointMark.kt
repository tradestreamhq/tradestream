package com.verlumen.tradestream.marketdata

 import org.apache.beam.sdk.io.UnboundedSource
 import org.joda.time.Instant
 import java.io.Serializable

 /**
  * Checkpoint mark for the exchange client trade source using Kotlin data class.
  * Stores the timestamp of the last successfully processed trade.
  */
 data class TradeCheckpointMark(
     // Default to EPOCH, ensuring non-null
     val lastProcessedTimestamp: Instant = Instant.EPOCH
 ) : UnboundedSource.CheckpointMark, Serializable {

     companion object {
         private const val serialVersionUID = 1L
         // Define INITIAL using the primary constructor's default
         @JvmField // Expose as public static final field for Java
         val INITIAL = TradeCheckpointMark() 
     }

     override fun finalizeCheckpoint() {
         // No-op for this simple checkpoint
     }

     // equals() and hashCode() are automatically generated by data class
 }
