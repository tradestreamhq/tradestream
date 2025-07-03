package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.protobuf.Any
import com.google.protobuf.Timestamp
import com.verlumen.tradestream.discovery.StrategyCsvUtil
import com.verlumen.tradestream.sql.BulkCopierFactory
import com.verlumen.tradestream.sql.DataSourceConfig
import com.verlumen.tradestream.sql.DataSourceFactory
import com.verlumen.tradestream.strategies.Strategy
import org.json.JSONObject
import java.io.Serializable
import java.io.StringReader
import java.sql.ResultSet
import javax.sql.DataSource

class PostgresStrategyRepository
    @Inject
    constructor(
        private val bulkCopierFactory: BulkCopierFactory,
        private val dataSourceFactory: DataSourceFactory,
        private val dataSourceConfig: DataSourceConfig,
    ) : StrategyRepository,
        Serializable {
        companion object {
            private val logger = FluentLogger.forEnclosingClass()
            private const val serialVersionUID: Long = 1L
        }

        private val dataSource: DataSource by lazy { dataSourceFactory.create(dataSourceConfig) }

        /**
         * Factory implementation for PostgresStrategyRepository
         */
        class Factory
            @Inject
            constructor(
                private val bulkCopierFactory: BulkCopierFactory,
                private val dataSourceFactory: DataSourceFactory,
            ) : StrategyRepository.Factory {
                override fun create(dataSourceConfig: DataSourceConfig): StrategyRepository =
                    PostgresStrategyRepository(bulkCopierFactory, dataSourceFactory, dataSourceConfig)
            }

        override fun save(strategy: DiscoveredStrategy) {
            saveAll(listOf(strategy))
        }

        override fun saveAll(strategies: List<DiscoveredStrategy>) {
            if (strategies.isEmpty()) return
            dataSource.connection.use { conn ->
                conn.autoCommit = false
                val batchData = strategies.mapNotNull { StrategyCsvUtil.convertToCsvRow(it) }
                if (batchData.isEmpty()) return
                val createTempTableSql =
                    """
                    CREATE TEMP TABLE temp_strategies (
                        symbol VARCHAR,
                        strategy_type VARCHAR,
                        parameters JSONB,
                        current_score DOUBLE PRECISION,
                        strategy_hash VARCHAR,
                        discovery_symbol VARCHAR,
                        discovery_start_time TIMESTAMP,
                        discovery_end_time TIMESTAMP
                    ) ON COMMIT DROP
                    """.trimIndent()
                conn.prepareStatement(createTempTableSql).use { it.execute() }
                val copyManager = bulkCopierFactory.create(conn)
                val csvData = batchData.joinToString("\n")
                copyManager.copy("temp_strategies", StringReader(csvData))
                val upsertSql =
                    """
                    INSERT INTO Strategies (
                        strategy_id, symbol, strategy_type, parameters,
                        first_discovered_at, last_evaluated_at, current_score,
                        is_active, strategy_hash, discovery_symbol,
                        discovery_start_time, discovery_end_time
                    )
                    SELECT
                        gen_random_uuid(), symbol, strategy_type, parameters,
                        NOW(), NOW(), current_score, TRUE, strategy_hash,
                        discovery_symbol, discovery_start_time, discovery_end_time
                    FROM temp_strategies
                    ON CONFLICT (strategy_hash) DO UPDATE SET
                        current_score = EXCLUDED.current_score,
                        last_evaluated_at = NOW()
                    """.trimIndent()
                conn.prepareStatement(upsertSql).use { it.execute() }
                conn.commit()
            }
        }

        override fun findBySymbol(symbol: String): List<DiscoveredStrategy> {
            val result = mutableListOf<DiscoveredStrategy>()
            dataSource.connection.use { conn ->
                val sql =
                    """
                    SELECT symbol, strategy_type, parameters, current_score, strategy_hash, 
                           discovery_symbol, discovery_start_time, discovery_end_time 
                    FROM Strategies WHERE symbol = ?
                    """.trimIndent()
                conn.prepareStatement(sql).use { stmt ->
                    stmt.setString(1, symbol)
                    val rs = stmt.executeQuery()
                    while (rs.next()) {
                        result.add(mapRowToDiscoveredStrategy(rs))
                    }
                }
            }
            return result
        }

        override fun findAll(): List<DiscoveredStrategy> {
            val result = mutableListOf<DiscoveredStrategy>()
            dataSource.connection.use { conn ->
                val sql =
                    """
                    SELECT symbol, strategy_type, parameters, current_score, strategy_hash, 
                           discovery_symbol, discovery_start_time, discovery_end_time 
                    FROM Strategies
                    """.trimIndent()
                conn.prepareStatement(sql).use { stmt ->
                    val rs = stmt.executeQuery()
                    while (rs.next()) {
                        result.add(mapRowToDiscoveredStrategy(rs))
                    }
                }
            }
            return result
        }

        private fun mapRowToDiscoveredStrategy(rs: ResultSet): DiscoveredStrategy {
            val symbol = rs.getString("symbol")
            val strategyType = rs.getString("strategy_type")
            val parametersJson = rs.getString("parameters")
            val score = rs.getDouble("current_score")
            val startTime = rs.getTimestamp("discovery_start_time")
            val endTime = rs.getTimestamp("discovery_end_time")

            // Parse parameters JSON and decode base64
            val jsonObj = JSONObject(parametersJson)
            val base64 = jsonObj.getString("base64_data")
            val bytes =
                java.util.Base64
                    .getDecoder()
                    .decode(base64)
            val parametersAny =
                com.google.protobuf.Any
                    .parseFrom(bytes)

            // Build Strategy proto
            val strategy =
                com.verlumen.tradestream.strategies.Strategy
                    .newBuilder()
                    .setTypeValue(
                        com.verlumen.tradestream.strategies.StrategyType
                            .valueOf(strategyType)
                            .number,
                    ).setParameters(parametersAny)
                    .build()

            // Build DiscoveredStrategy proto
            return DiscoveredStrategy
                .newBuilder()
                .setStrategy(strategy)
                .setScore(score)
                .setSymbol(symbol)
                .setStartTime(
                    com.google.protobuf.Timestamp
                        .newBuilder()
                        .setSeconds(startTime.time / 1000)
                        .build(),
                ).setEndTime(
                    com.google.protobuf.Timestamp
                        .newBuilder()
                        .setSeconds(endTime.time / 1000)
                        .build(),
                ).build()
        }
    }
