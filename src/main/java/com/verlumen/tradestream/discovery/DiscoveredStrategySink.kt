package com.verlumen.tradestream.discovery

import com.google.fluentlogging.FluentLogger
import com.verlumen.tradestream.discovery.proto.DiscoveredStrategy
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.PDone

/**
 * A sink for discovered strategies. Implementations should handle persisting strategies to their
 * respective storage systems.
 */
interface DiscoveredStrategySink : PTransform<PCollection<DiscoveredStrategy>, PDone> {
    companion object {
        private val logger = FluentLogger.forEnclosingClass()
    }
}
