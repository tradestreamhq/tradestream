package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.discovery.DiscoveredStrategy
import com.verlumen.tradestream.sql.DataSourceConfig

interface StrategyRepository {
    fun save(strategy: DiscoveredStrategy)

    fun saveAll(strategies: List<DiscoveredStrategy>)

    fun findBySymbol(symbol: String): List<DiscoveredStrategy>

    fun findAll(): List<DiscoveredStrategy>

    /**
     * Factory interface for assisted injection
     */
    interface Factory {
        fun create(dataSourceConfig: DataSourceConfig): StrategyRepository
    }
}
