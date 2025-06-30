package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.discovery.DiscoveredStrategySinkParams
import org.apache.beam.sdk.transforms.DoFn

/**
 * Abstract base class for writing discovered strategies to a sink.
 *
 * This abstraction allows for different sink implementations (e.g., Kafka, PostgreSQL, dry-run).
 */
abstract class DiscoveredStrategySink : DoFn<DiscoveredStrategy, Void>()

/**
 * Factory for creating [DiscoveredStrategySink] instances.
 *
 * This factory uses a unified parameter structure to create different types of sinks:
 * - Postgres sink: requires DataSourceConfig
 * - Kafka sink: requires bootstrap servers and topic
 * - Dry-run sink: requires no additional parameters
 */
interface DiscoveredStrategySinkFactory {
    fun create(params: DiscoveredStrategySinkParams): DiscoveredStrategySink
}
