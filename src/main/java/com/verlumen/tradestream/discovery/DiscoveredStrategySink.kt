package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.discovery.DiscoveredStrategy
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.PDone

/**
 * Interface for sinks that write discovered strategies to a destination.
 * Implementations should handle the actual writing logic (e.g., to a database, file, etc.).
 */
interface DiscoveredStrategySink {
    fun expand(input: PCollection<DiscoveredStrategy>): PDone
}
