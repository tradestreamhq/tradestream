package com.verlumen.tradestream.discovery

import com.google.fluentlogging.FluentLogger
import com.google.inject.Inject
import com.verlumen.tradestream.discovery.proto.DiscoveredStrategy
import com.verlumen.tradestream.sql.DataSourceConfig
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.PDone

class PostgresDiscoveredStrategySink @Inject constructor(
    private val dataSourceConfig: DataSourceConfig,
) : DiscoveredStrategySink {
    companion object {
        private val logger = FluentLogger.forEnclosingClass()
    }

    override fun expand(input: PCollection<DiscoveredStrategy>): PDone {
        logger.atInfo().log("Writing discovered strategies to Postgres")
        return input.apply(
            ParDo.of(
                WriteDiscoveredStrategiesToPostgresFn.create(dataSourceConfig),
            ),
        )
    }
} 