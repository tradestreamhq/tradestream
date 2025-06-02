package com.verlumen.tradestream.discovery

import org.apache.beam.runners.flink.FlinkPipelineOptions // Assuming Flink runner as per existing setup hints
import org.apache.beam.sdk.options.Default
import org.apache.beam.sdk.options.Description
import org.apache.beam.sdk.options.PipelineOptions
import org.apache.beam.sdk.options.StreamingOptions

interface StrategyDiscoveryPipelineOptions :
    PipelineOptions,
    FlinkPipelineOptions,
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
    var influxDbToken: String? // Made nullable as it might come from secrets

    @get:Description("InfluxDB organization")
    @get:Default.String("tradestream-org")
    var influxDbOrg: String

    @get:Description("InfluxDB bucket for candle data")
    @get:Default.String("tradestream-data")
    var influxDbBucket: String

    @get:Description("Database JDBC URL for writing results (e.g., jdbc:postgresql://localhost:5432/tradestream)")
    var databaseJdbcUrl: String?

    @get:Description("Database username")
    var databaseUsername: String?

    @get:Description("Database password")
    var databasePassword: String?
}
