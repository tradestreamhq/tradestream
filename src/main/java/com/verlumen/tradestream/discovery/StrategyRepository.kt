package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.discovery.DiscoveredStrategy
import com.verlumen.tradestream.sql.DataSourceConfig
import java.io.Serializable

interface StrategyRepository : Serializable {
    fun save(strategy: DiscoveredStrategy)

    fun saveAll(strategies: List<DiscoveredStrategy>)

    fun findBySymbol(symbol: String): List<DiscoveredStrategy>

    fun findAll(): List<DiscoveredStrategy>

    /**
     * Factory interface for assisted injection and Beam serialization
     */
    interface Factory : Serializable {
        fun create(dataSourceConfig: DataSourceConfig): StrategyRepository
    }
}
