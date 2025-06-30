package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.verlumen.tradestream.sql.DataSourceConfig

/**
 * A dry-run implementation of [DiscoveredStrategySink] that logs the strategies
 * instead of writing them to a persistent store.
 */
class DryRunDiscoveredStrategySink
    @Inject
    constructor(
        @Assisted private val dataSourceConfig: DataSourceConfig,
    ) : DiscoveredStrategySink() {
        @ProcessElement
        fun processElement(context: ProcessContext) {
            val strategy = context.element()
            logger.atInfo().log("Dry Run Sink: Would write strategy for symbol '%s' with score %f", strategy.symbol, strategy.score)
        }

        companion object {
            private val logger = FluentLogger.forEnclosingClass()
        }
    }
