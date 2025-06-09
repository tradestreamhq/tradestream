package com.verlumen.tradestream.discovery

import com.google.common.collect.ImmutableList
import com.google.inject.assistedinject.AssistedFactory
import com.google.inject.assistedinject.AssistedInject
import com.verlumen.tradestream.execution.RunMode
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.PInput

/**
 * Interface for sources of strategy discovery requests.
 * Different implementations can provide requests from different sources (e.g., Kafka, dry run).
 */
interface DiscoveryRequestSource : PTransform<PInput, PCollection<StrategyDiscoveryRequest>> {
    @AssistedFactory
    interface Factory {
        fun create(runMode: RunMode): DiscoveryRequestSource
    }
} 