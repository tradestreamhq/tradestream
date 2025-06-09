package com.verlumen.tradestream.discovery

import org.apache.beam.sdk.options.Default
import org.apache.beam.sdk.options.Description
import org.apache.beam.sdk.options.PipelineOptions
import org.apache.beam.sdk.options.StreamingOptions

/**
 * Runtime flags for the strategy-discovery job.
 *
 * All fields are regular PipelineOptions so the
 * same JAR can run on any Beam runner (Direct, Flink,
 * Dataflow, Spark, etc.).  We keep StreamingOptions
 * to mark the job as unbounded.
 */
interface StrategyDiscoveryPipelineOptions :
    PipelineOptions,
    StreamingOptions {
    @get:Description("Kafka bootstrap servers")
    @get:Default.String("localhost:9092")
    var kafkaBootstrapServers: String

    @get:Description("Kafka topic for StrategyDiscoveryRequest messages")
    @get:Default.String("strategy-discovery-requests")
    var strategyDiscoveryRequestTopic: String

    @get:Description("InfluxDB URL for fetching candle data")
    @get:Default.String("http://localhost:8086")
    var influxDbUrl: String

    @get:Description("InfluxDB token")
    var influxDbToken: String?

    @get:Description("InfluxDB organization")
    @get:Default.String("tradestream-org")
    var influxDbOrg: String

    @get:Description("InfluxDB bucket for candle data")
    @get:Default.String("tradestream-data")
    var influxDbBucket: String

    @get:Description("PostgreSQL server name for writing results")
    @get:Default.String("localhost")
    var dbServerName: String

    @get:Description("PostgreSQL database name for writing results")
    @get:Default.String("tradestream")
    var dbDatabaseName: String

    @get:Description("PostgreSQL port for writing results")
    @get:Default.Integer(5432)
    var dbPortNumber: Int

    @get:Description("Database username")
    var databaseUsername: String?

    @get:Description("Database password")
    var databasePassword: String?

    @get:Description("Whether to run in dry run mode (no Kafka/Postgres)")
    @get:Default.Boolean(false)
    var dryRun: Boolean
}
