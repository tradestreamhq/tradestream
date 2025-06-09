package com.verlumen.tradestream.discovery

import com.google.common.collect.ImmutableList
import com.google.common.flogger.FluentLogger
import com.google.inject.assistedinject.Assisted
import com.google.inject.assistedinject.AssistedInject
import com.google.protobuf.Timestamp
import com.verlumen.tradestream.execution.RunMode
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.PInput
import java.time.Instant

/**
 * A dry run implementation of DiscoveryRequestSource that generates test requests.
 * This is useful for testing the strategy discovery pipeline without affecting production data.
 */
class DryRunDiscoveryRequestSource
    @AssistedInject
    constructor(
        @Assisted private val runMode: RunMode,
    ) : DiscoveryRequestSource {
        companion object {
            private val logger = FluentLogger.forEnclosingClass()
        }

        override fun expand(input: PInput): PCollection<StrategyDiscoveryRequest> {
            logger.atInfo().log("Creating dry run discovery requests")

            val now = Instant.now()
            val startTime = now.minus(java.time.Duration.ofDays(30))
            val endTime = now

            val requests =
                ImmutableList.of(
                    createRequest(
                        symbol = "BTC/USD",
                        strategyType = StrategyType.SMA_RSI,
                        startTime = startTime,
                        endTime = endTime,
                    ),
                    createRequest(
                        symbol = "ETH/USD",
                        strategyType = StrategyType.EMA_MACD,
                        startTime = startTime,
                        endTime = endTime,
                    ),
                    createRequest(
                        symbol = "SOL/USD",
                        strategyType = StrategyType.ADX_STOCHASTIC,
                        startTime = startTime,
                        endTime = endTime,
                    ),
                )

            return input.pipeline.apply(Create.of(requests))
        }

        private fun createRequest(
            symbol: String,
            strategyType: StrategyType,
            startTime: Instant,
            endTime: Instant,
        ): StrategyDiscoveryRequest =
            StrategyDiscoveryRequest
                .newBuilder()
                .setSymbol(symbol)
                .setStrategyType(strategyType)
                .setStartTime(
                    Timestamp
                        .newBuilder()
                        .setSeconds(startTime.epochSecond)
                        .setNanos(startTime.nano)
                        .build(),
                ).setEndTime(
                    Timestamp
                        .newBuilder()
                        .setSeconds(endTime.epochSecond)
                        .setNanos(endTime.nano)
                        .build(),
                ).setTopN(5)
                .setGaConfig(
                    GAConfig
                        .newBuilder()
                        .setMaxGenerations(10)
                        .setPopulationSize(100)
                        .build(),
                ).build()
    } 
