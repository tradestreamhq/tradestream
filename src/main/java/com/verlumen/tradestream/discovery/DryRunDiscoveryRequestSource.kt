package com.verlumen.tradestream.discovery

import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.google.protobuf.Timestamp
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.PBegin
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.KV
import java.time.Instant
import java.time.temporal.ChronoUnit

/**
 * Dry run implementation of DiscoveryRequestSource that creates a predefined list of 
 * strategy discovery requests in memory for testing purposes.
 */
class DryRunDiscoveryRequestSource
    @Inject
    constructor(
        private val deserializeFn: DeserializeStrategyDiscoveryRequestFn,
        @Assisted private val options: StrategyDiscoveryPipelineOptions,
    ) : DiscoveryRequestSource() {
        
    override fun expand(input: PBegin): PCollection<StrategyDiscoveryRequest> {
        // Create sample discovery requests in memory
        val sampleRequests = createSampleRequests()
        
        return input.pipeline
            .apply(
                "CreateDiscoveryRequestsInMemory",
                Create.of(sampleRequests)
            ).apply(
                "DeserializeProtoRequests", 
                ParDo.of(deserializeFn)
            )
    }
    
    /**
     * Creates a list of sample KV pairs representing serialized discovery requests.
     * In a real scenario, these would be the same format as what comes from Kafka.
     */
    private fun createSampleRequests(): List<KV<String, ByteArray>> {
        val now = Instant.now()
        val startTime = now.minus(30, ChronoUnit.DAYS)
        val endTime = now
        
        return listOf(
            KV.of("request-1", createSampleRequestBytes("BTCUSDT", StrategyType.SMA_RSI, startTime, endTime, 5)),
            KV.of("request-2", createSampleRequestBytes("ETHUSDT", StrategyType.EMA_MACD, startTime, endTime, 3)),
            KV.of("request-3", createSampleRequestBytes("AAPL", StrategyType.MACD_CROSSOVER, startTime, endTime, 10)),
            KV.of("request-4", createSampleRequestBytes("TSLA", StrategyType.DOUBLE_EMA_CROSSOVER, startTime, endTime, 7)),
            KV.of("request-5", createSampleRequestBytes("GOOGL", StrategyType.VWAP_CROSSOVER, startTime, endTime, 5)),
            KV.of("request-6", createSampleRequestBytes("ADAUSDT", StrategyType.PARABOLIC_SAR, startTime, endTime, 8)),
            KV.of("request-7", createSampleRequestBytes("SPY", StrategyType.BBAND_W_R, startTime, endTime, 6)),
            KV.of("request-8", createSampleRequestBytes("QQQ", StrategyType.RSI_EMA_CROSSOVER, startTime, endTime, 4))
        )
    }
    
    /**
     * Creates sample serialized request bytes. This creates actual protobuf bytes
     * that would match what comes from the Kafka topic in the real implementation.
     */
    private fun createSampleRequestBytes(
        symbol: String,
        strategyType: StrategyType,
        startTime: Instant,
        endTime: Instant,
        topN: Int
    ): ByteArray {
        val startTimestamp = Timestamp.newBuilder()
            .setSeconds(startTime.epochSecond)
            .setNanos(startTime.nano)
            .build()
            
        val endTimestamp = Timestamp.newBuilder()
            .setSeconds(endTime.epochSecond)
            .setNanos(endTime.nano)
            .build()
            
        val gaConfig = GAConfig.newBuilder()
            .setMaxGenerations(50)
            .setPopulationSize(100)
            .build()
        
        val request = StrategyDiscoveryRequest.newBuilder()
            .setSymbol(symbol)
            .setStartTime(startTimestamp)
            .setEndTime(endTimestamp)
            .setStrategyType(strategyType)
            .setTopN(topN)
            .setGaConfig(gaConfig)
            .build()
            
        return request.toByteArray()
    }
}
