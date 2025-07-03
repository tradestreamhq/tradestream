package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.sql.DataSourceConfig

/**
 * Sealed class representing unified parameters for discovered strategy sinks.
 *
 * This provides a type-safe way to configure different sink implementations
 * while maintaining a unified interface for the factory.
 */
sealed class DiscoveredStrategySinkParams {
    data class Postgres(
        val config: DataSourceConfig,
    ) : DiscoveredStrategySinkParams()

    data class Kafka(
        val bootstrapServers: String,
        val topic: String,
    ) : DiscoveredStrategySinkParams()

    object DryRun : DiscoveredStrategySinkParams()
}
