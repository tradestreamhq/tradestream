package com.verlumen.tradestream.discovery

import com.google.inject.Inject
import com.google.inject.Provider
import com.verlumen.tradestream.execution.RunMode
import com.verlumen.tradestream.strategies.StrategyType

class DiscoveryRequestSourceProvider
    @Inject
    constructor(
        private val config: DiscoveryConfig,
        private val dryRunFactory: DryRunDiscoveryRequestSource.Factory,
        private val kafkaFactory: KafkaDiscoveryRequestSource.Factory,
    ) : Provider<DiscoveryRequestSource> {
        override fun get(): DiscoveryRequestSource =
            when (config.runMode) {
                RunMode.DRY ->
                    dryRunFactory.create(
                        symbol = "BTC/USD",
                        strategyType = StrategyType.SMA_RSI,
                    )
                RunMode.WET ->
                    kafkaFactory.create(
                        bootstrapServers = config.kafkaConfig.bootstrapServers,
                        topic = config.kafkaConfig.topic,
                        groupId = config.kafkaConfig.groupId,
                    )
            }
    }
