package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.protobuf.util.JsonFormat
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.PCollection

/**
 * A PTransform that parses StrategyDiscoveryRequest messages from Kafka JSON strings.
 */
class ParseDiscoveryRequests : PTransform<PCollection<String>, PCollection<StrategyDiscoveryRequest>>() {
    override fun expand(input: PCollection<String>): PCollection<StrategyDiscoveryRequest> =
        input.apply(ParDo.of(ParseDiscoveryRequestsFn()))

    private class ParseDiscoveryRequestsFn : DoFn<String, StrategyDiscoveryRequest>() {
        companion object {
            private val logger = FluentLogger.forEnclosingClass()
        }

        @ProcessElement
        fun processElement(c: ProcessContext) {
            val json = c.element()
            try {
                val request = StrategyDiscoveryRequest.newBuilder()
                JsonFormat.parser().merge(json, request)
                c.output(request.build())
            } catch (e: Exception) {
                logger.atWarning().withCause(e).log("Failed to parse discovery request: $json")
            }
        }
    }
}
