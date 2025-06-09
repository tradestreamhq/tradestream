package com.verlumen.tradestream.discovery

import com.google.inject.Inject
import com.google.inject.Provider
import com.verlumen.tradestream.execution.RunMode

class DiscoveryRequestSourceProvider
    @Inject
    constructor(
        private val config: DiscoveryConfig,
    ) : Provider<DiscoveryRequestSource> {
        override fun get(): DiscoveryRequestSource =
            when (config.runMode) {
                RunMode.DRY -> DryRunDiscoveryRequestSource()
                RunMode.WET -> KafkaDiscoveryRequestSource()
            }
    } 
