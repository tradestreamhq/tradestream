package com.verlumen.tradestream.discovery

import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.values.PBegin
import org.apache.beam.sdk.values.PCollection

/**
 * Abstract base class for reading strategy discovery requests from various sources.
 * 
 * This abstraction replaces the first few steps of the strategy discovery pipeline,
 * allowing different source implementations (Kafka, files, etc.) while keeping
 * the rest of the pipeline unchanged.
 */
abstract class DiscoveryRequestSource : PTransform<PBegin, PCollection<StrategyDiscoveryRequest>>()

/**
 * Factory interface for creating DiscoveryRequestSource instances with 
 * runtime-provided configuration parameters.
 */
interface DiscoveryRequestSourceFactory {
    fun create(options: StrategyDiscoveryPipelineOptions): DiscoveryRequestSource
}
