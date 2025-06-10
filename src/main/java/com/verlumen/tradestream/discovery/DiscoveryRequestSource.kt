package com.verlumen.tradestream.discovery

import com.google.inject.assistedinject.Assisted
import com.google.inject.assistedinject.AssistedInject
import com.verlumen.tradestream.execution.RunMode
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.PInput

/**
 * Interface for sources of strategy discovery requests.
 * Different implementations can provide requests from different sources (e.g., Kafka, dry run).
 */
interface DiscoveryRequestSource : PTransform<PInput, PCollection<StrategyDiscoveryRequest>> {
    interface Factory {
        fun create(@Assisted runMode: RunMode): DiscoveryRequestSource
    }
}
