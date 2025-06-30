package com.verlumen.tradestream.discovery

import com.google.inject.Inject

class KafkaSinkFactoryImpl
    @Inject
    constructor(
        private val writeDiscoveredStrategiesToKafkaFactory: WriteDiscoveredStrategiesToKafkaFactory,
    ) : DiscoveredStrategySinkFactory {
        override fun create(params: DiscoveredStrategySinkParams): DiscoveredStrategySink {
            val kafkaParams = params as DiscoveredStrategySinkParams.Kafka
            return writeDiscoveredStrategiesToKafkaFactory.create(kafkaParams.bootstrapServers, kafkaParams.topic)
        }
    } 