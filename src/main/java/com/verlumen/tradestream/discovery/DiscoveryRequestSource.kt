package com.verlumen.tradestream.discovery

import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.values.PBegin
import org.apache.beam.sdk.values.PCollection
import java.io.Serializable

/**
 * Abstract transformation that reads strategy discovery requests from a source
 * and outputs deserialized StrategyDiscoveryRequest objects.
 *
 * This abstraction allows the pipeline to support different sources for strategy
 * discovery requests (Kafka, files, etc.) without changing the core pipeline logic.
 */
abstract class DiscoveryRequestSource : PTransform<PBegin, PCollection<StrategyDiscoveryRequest>>, Serializable {
    
    companion object {
        private const val serialVersionUID = 1L
    }
}

/**
 * Factory interface for creating DiscoveryRequestSource instances with runtime configuration.
 */
interface DiscoveryRequestSourceFactory {
    /**
     * Creates a DiscoveryRequestSource configured with the given pipeline options.
     */
    fun create(options: StrategyDiscoveryPipelineOptions): DiscoveryRequestSource
}
