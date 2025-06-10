package com.verlumen.tradestream.discovery

import com.google.inject.assistedinject.Assisted
import com.google.inject.assistedinject.AssistedInject
import com.google.protobuf.Timestamp
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.values.PBegin
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.PInput

/**
 * A source that generates a single discovery request for testing/dry run purposes.
 */
class DryRunDiscoveryRequestSource
    @AssistedInject
    constructor(
        @Assisted private val symbol: String,
        @Assisted private val strategyType: StrategyType,
    ) : PTransform<PBegin, PCollection<StrategyDiscoveryRequest>>(),
        DiscoveryRequestSource {
    companion object {
        private const val DEFAULT_TOP_N = 10
        private const val DEFAULT_MAX_GENERATIONS = 50
        private const val DEFAULT_POPULATION_SIZE = 100
    }

    override fun expand(input: Any): PCollection<StrategyDiscoveryRequest> {
        return expand(input as PBegin)
    }

    override fun expand(input: PBegin): PCollection<StrategyDiscoveryRequest> {
        val request =
            StrategyDiscoveryRequest
                .newBuilder()
                .setSymbol(symbol)
                .setStartTime(Timestamp.newBuilder().setSeconds((System.currentTimeMillis() - 100000) / 1000).build())
                .setEndTime(Timestamp.newBuilder().setSeconds(System.currentTimeMillis() / 1000).build())
                .setStrategyType(strategyType)
                .setTopN(DEFAULT_TOP_N)
                .setGaConfig(
                    GAConfig
                        .newBuilder()
                        .setMaxGenerations(DEFAULT_MAX_GENERATIONS)
                        .setPopulationSize(DEFAULT_POPULATION_SIZE)
                        .build(),
                ).build()

        return input.pipeline.apply(Create.of(listOf(request)))
    }

    /**
     * Factory interface for assisted injection
     */
    interface Factory {
        fun create(
            symbol: String,
            strategyType: StrategyType,
        ): DryRunDiscoveryRequestSource
    }
}
