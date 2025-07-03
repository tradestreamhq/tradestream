package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.verlumen.tradestream.sql.DataSourceConfig
import java.io.Serializable

/**
 * A dry-run implementation of StrategyRepository that logs operations
 * instead of persisting data to a database.
 */
class DryRunStrategyRepository :
    StrategyRepository,
    Serializable {
    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val serialVersionUID: Long = 1L
    }

    override fun save(strategy: DiscoveredStrategy) {
        logger.atInfo().log("Dry Run: Would save strategy for symbol '%s' with score %f", strategy.symbol, strategy.score)
    }

    override fun saveAll(strategies: List<DiscoveredStrategy>) {
        logger.atInfo().log("Dry Run: Would save %d strategies", strategies.size)
        strategies.forEach { strategy ->
            logger.atInfo().log("Dry Run: Would save strategy for symbol '%s' with score %f", strategy.symbol, strategy.score)
        }
    }

    override fun findBySymbol(symbol: String): List<DiscoveredStrategy> {
        logger.atInfo().log("Dry Run: Would find strategies for symbol '%s'", symbol)
        return emptyList()
    }

    override fun findAll(): List<DiscoveredStrategy> {
        logger.atInfo().log("Dry Run: Would find all strategies")
        return emptyList()
    }

    /**
     * Factory implementation for DryRunStrategyRepository
     */
    class Factory
        @Inject
        constructor() : StrategyRepository.Factory {
            override fun create(dataSourceConfig: DataSourceConfig): StrategyRepository = DryRunStrategyRepository()
        }
}
