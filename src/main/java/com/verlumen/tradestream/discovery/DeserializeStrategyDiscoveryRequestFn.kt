package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.common.flogger.FluentLogger
import com.google.common.flogger.FluentLogger
import com.verlumen.tradestream.discovery.proto.Discovery.StrategyDiscoveryRequest
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.values.KV

/**
 * Apache Beam transform that deserializes Kafka messages containing
 * StrategyDiscoveryRequest protobuf messages.
 *
 * Input: KV<String, ByteArray> from Kafka
 * Output: StrategyDiscoveryRequest proto objects
 *
 * Handles deserialization errors gracefully by logging and dropping invalid messages.
 */
class DeserializeStrategyDiscoveryRequestFn : DoFn<KV<String, ByteArray>, StrategyDiscoveryRequest>() {
    companion object {
        private val logger = FluentLogger.forEnclosingClass()
    }

    @ProcessElement
    fun processElement(context: ProcessContext) {
        val kafkaValue = context.element().value
        if (kafkaValue != null) {
            try {
                val request = StrategyDiscoveryRequest.parseFrom(kafkaValue)
                context.output(request)
            } catch (e: InvalidProtocolBufferException) {
                logger
                    .atSevere()
                    .withCause(e)
                    .log("Failed to deserialize StrategyDiscoveryRequest proto.")
            }
        }
    }
}
