package com.verlumen.tradestream.discovery

import org.apache.beam.sdk.values.PCollection

/**
 * Interface for sources that provide strategy discovery requests.
 * Implementations should handle the actual source of requests (e.g., Kafka, dry run, etc.).
 */
interface DiscoveryRequestSource {
    /**
     * Expands this source into a PCollection of strategy discovery requests.
     * The input type is implementation-specific.
     */
    fun expand(input: Any): PCollection<StrategyDiscoveryRequest>
}
