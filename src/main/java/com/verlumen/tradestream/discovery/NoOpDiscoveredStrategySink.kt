package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.verlumen.tradestream.discovery.DiscoveredStrategy
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.PDone

class NoOpDiscoveredStrategySink : DiscoveredStrategySink {
    companion object {
        private val logger = FluentLogger.forEnclosingClass()
    }

    override fun expand(input: PCollection<DiscoveredStrategy>): PDone {
        val pipeline = input.pipeline
        input.apply(
            ParDo.of(
                object : DoFn<DiscoveredStrategy, Void>() {
                    @ProcessElement
                    fun processElement(
                        @Element strategy: DiscoveredStrategy,
                    ) {
                        logger.atInfo().log(
                            "Would persist strategy: type=${strategy.strategy.type}, " +
                                "score=${strategy.score}, symbol=${strategy.symbol}",
                        )
                    }
                },
            ),
        )
        return PDone.in(pipeline)
    }
}
