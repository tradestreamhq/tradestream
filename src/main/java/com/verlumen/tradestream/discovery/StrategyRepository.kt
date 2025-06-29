package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.discovery.DiscoveredStrategy

interface StrategyRepository {
    fun save(strategy: DiscoveredStrategy)

    fun saveAll(strategies: List<DiscoveredStrategy>)

    fun findBySymbol(symbol: String): List<DiscoveredStrategy>

    fun findAll(): List<DiscoveredStrategy>
}
