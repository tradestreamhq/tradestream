package com.verlumen.tradestream.backtesting

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.inject.name.Named
import io.grpc.ManagedChannel
import io.grpc.ManagedChannelBuilder
import io.grpc.StatusRuntimeException
import io.grpc.netty.shaded.io.grpc.netty.GrpcSslContexts
import io.grpc.netty.shaded.io.grpc.netty.NettyChannelBuilder
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Remote implementation of BacktestRunner that calls the Backtesting gRPC Service.
 *
 * This client enables the Strategy Discovery Pipeline (running on Java 17/Flink)
 * to offload backtesting to the standalone Backtesting Service (running on Java 21).
 *
 * TLS is enabled when the TLS_CA_CERT_PATH environment variable is set.
 *
 * Usage:
 * 1. Create with Guice injection (preferred):
 *    ```kotlin
 *    @Inject
 *    constructor(
 *        @Named("backtesting.service.host") host: String,
 *        @Named("backtesting.service.port") port: Int
 *    )
 *    ```
 *
 * 2. Create directly:
 *    ```kotlin
 *    RemoteBacktestRunner.create("localhost", 50051)
 *    ```
 */
class RemoteBacktestRunner
    @Inject
    constructor(
        @Named("backtesting.service.host") private val host: String,
        @Named("backtesting.service.port") private val port: Int,
    ) : BacktestRunner {
        companion object {
            private val logger = FluentLogger.forEnclosingClass()
            private const val DEFAULT_DEADLINE_SECONDS = 60L

            /**
             * Factory method for creating a RemoteBacktestRunner.
             */
            @JvmStatic
            fun create(
                host: String,
                port: Int,
            ): RemoteBacktestRunner = RemoteBacktestRunner(host, port)
        }

        private val channel: ManagedChannel by lazy {
            logger.atInfo().log("Creating gRPC channel to %s:%d", host, port)
            val caCertPath = System.getenv("TLS_CA_CERT_PATH")
            if (caCertPath != null) {
                val caCertFile = File(caCertPath)
                require(caCertFile.exists()) { "TLS CA certificate not found: $caCertPath" }
                logger.atInfo().log("Configuring TLS with CA cert=%s", caCertPath)
                val sslContext =
                    GrpcSslContexts
                        .forClient()
                        .trustManager(caCertFile)
                        .build()
                NettyChannelBuilder
                    .forAddress(host, port)
                    .sslContext(sslContext)
                    .build()
            } else {
                logger.atWarning().log(
                    "TLS not configured (TLS_CA_CERT_PATH not set). Using plaintext.",
                )
                ManagedChannelBuilder
                    .forAddress(host, port)
                    .usePlaintext()
                    .build()
            }
        }

        private val blockingStub: BacktestingServiceGrpc.BacktestingServiceBlockingStub by lazy {
            BacktestingServiceGrpc.newBlockingStub(channel)
        }

        override fun runBacktest(request: BacktestRequest): BacktestResult {
            try {
                logger.atFine().log(
                    "Sending backtest request: strategy=%s, candles=%d",
                    request.strategy.strategyName,
                    request.candlesCount,
                )

                val result =
                    blockingStub
                        .withDeadlineAfter(DEFAULT_DEADLINE_SECONDS, TimeUnit.SECONDS)
                        .runBacktest(request)

                logger.atFine().log(
                    "Received backtest result: sharpe=%.4f, score=%.4f",
                    result.sharpeRatio,
                    result.strategyScore,
                )

                return result
            } catch (e: StatusRuntimeException) {
                logger.atWarning().withCause(e).log(
                    "gRPC call failed: status=%s, description=%s",
                    e.status.code,
                    e.status.description,
                )
                // Return a default result with negative infinity score for failed backtests
                return BacktestResult
                    .newBuilder()
                    .setStrategyScore(Double.NEGATIVE_INFINITY)
                    .build()
            }
        }

        /**
         * Runs batch backtests for multiple parameter sets of the same strategy.
         * This is optimized for GA fitness evaluation where many parameter combinations
         * need to be tested against the same candle data.
         *
         * @param request Batch backtest request containing candles and multiple strategies
         * @return Batch result containing all individual backtest results
         */
        fun runBatchBacktest(request: BatchBacktestRequest): BatchBacktestResult {
            try {
                logger.atFine().log(
                    "Sending batch backtest request: strategy=%s, batch_size=%d, candles=%d",
                    request.strategyName,
                    request.strategiesCount,
                    request.candlesCount,
                )

                val result =
                    blockingStub
                        .withDeadlineAfter(DEFAULT_DEADLINE_SECONDS * 2, TimeUnit.SECONDS) // Double deadline for batch
                        .runBatchBacktest(request)

                logger.atFine().log(
                    "Received batch backtest result: %d results",
                    result.resultsCount,
                )

                return result
            } catch (e: StatusRuntimeException) {
                logger.atWarning().withCause(e).log(
                    "Batch gRPC call failed: status=%s, description=%s",
                    e.status.code,
                    e.status.description,
                )
                // Return empty results for failed batch
                return BatchBacktestResult.getDefaultInstance()
            }
        }

        /**
         * Shuts down the gRPC channel gracefully.
         */
        fun shutdown() {
            logger.atInfo().log("Shutting down gRPC channel")
            try {
                channel.shutdown()
                if (!channel.awaitTermination(5, TimeUnit.SECONDS)) {
                    logger.atWarning().log("Channel did not terminate in time, forcing shutdown")
                    channel.shutdownNow()
                }
            } catch (e: InterruptedException) {
                logger.atWarning().log("Shutdown interrupted")
                channel.shutdownNow()
                Thread.currentThread().interrupt()
            }
        }
    }
