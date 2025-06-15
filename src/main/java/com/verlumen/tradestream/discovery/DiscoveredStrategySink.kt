package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.sql.DataSourceConfig
import org.apache.beam.sdk.transforms.DoFn

/**
 * Abstract base class for writing discovered strategies to a sink.
 *
 * This abstraction allows for different sink implementations (e.g., PostgreSQL, dry-run).
 */
abstract class DiscoveredStrategySink : DoFn<DiscoveredStrategy, Void>()

/**
 * Factory for creating [DiscoveredStrategySink] instances.
 */
interface DiscoveredStrategySinkFactory {
  fun create(dataSourceConfig: DataSourceConfig): DiscoveredStrategySink
}
