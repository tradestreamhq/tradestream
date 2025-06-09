package com.verlumen.tradestream.discovery

import com.google.fluentlogging.FluentLogger
import com.verlumen.tradestream.discovery.proto.DiscoveredStrategy
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.PDone

class NoOpDiscoveredStrategySink : DiscoveredStrategySink {
    companion object {
        private val logger = FluentLogger.forEnclosingClass()
    }

    override fun expand(input: PCollection<DiscoveredStrategy>): PDone {
        logger.atInfo().log("Dry run mode: skipping strategy persistence")
        return input.apply(
            ParDo.of(
                object : DoFn<DiscoveredStrategy, Void>() {
                    @ProcessElement
                    fun processElement(
                        @Element strategy: DiscoveredStrategy,
                    ) {
                        logger.atInfo().log("Would persist strategy: ${strategy.strategyId}")
                    }
                },
            ),
        )
    }
}
