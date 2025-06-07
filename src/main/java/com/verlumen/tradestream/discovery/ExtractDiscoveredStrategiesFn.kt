package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.discovery.proto.Discovery.DiscoveredStrategy
import com.verlumen.tradestream.discovery.proto.Discovery.StrategyDiscoveryResult
import org.apache.beam.sdk.transforms.DoFn

/**
 * Apache Beam transform that extracts individual discovered strategies from
 * StrategyDiscoveryResult objects.
 * 
 * Input: StrategyDiscoveryResult (containing multiple strategies)
 * Output: Individual DiscoveredStrategy objects
 * 
 * This flattens the result structure to enable individual processing
 * of each discovered strategy.
 */
class ExtractDiscoveredStrategiesFn : DoFn<StrategyDiscoveryResult, DiscoveredStrategy>() {
    
    @ProcessElement
    fun processElement(context: ProcessContext) {
        val result = context.element()
        result?.topStrategiesList?.forEach { strategy ->
            context.output(strategy)
        }
    }
}
