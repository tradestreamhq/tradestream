package com.verlumen.tradestream.backtestingservice

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.verlumen.tradestream.backtesting.BacktestRequest
import com.verlumen.tradestream.backtesting.BacktestResult
import com.verlumen.tradestream.backtesting.BacktestRunner
import com.verlumen.tradestream.backtesting.BacktestingServiceGrpc
import com.verlumen.tradestream.backtesting.BatchBacktestRequest
import com.verlumen.tradestream.backtesting.BatchBacktestResult
import com.verlumen.tradestream.backtesting.StrategyValidator
import com.verlumen.tradestream.backtesting.ValidationStatus
import com.verlumen.tradestream.backtesting.WalkForwardRequest
import com.verlumen.tradestream.backtesting.WalkForwardResult
import com.verlumen.tradestream.backtesting.WalkForwardRunner
import io.grpc.Status
import io.grpc.stub.StreamObserver
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * gRPC service implementation for the Backtesting Service.
 *
 * This service wraps the existing BacktestRunner to provide gRPC-based access
 * to backtesting functionality, enabling the Strategy Discovery Pipeline
 * (running on Java 17/Flink) to call this service (running on Java 21).
 */
class BacktestingGrpcService
    @Inject
    constructor(
        private val backtestRunner: BacktestRunner,
        private val walkForwardRunner: WalkForwardRunner,
        private val strategyValidator: StrategyValidator,
    ) : BacktestingServiceGrpc.BacktestingServiceImplBase() {
        companion object {
            private val logger = FluentLogger.forEnclosingClass()
            private const val BATCH_THREAD_POOL_SIZE = 8
        }

        private val batchExecutor = Executors.newFixedThreadPool(BATCH_THREAD_POOL_SIZE)

        /**
         * Runs a single backtest for the given strategy and candle data.
         */
        override fun runBacktest(
            request: BacktestRequest,
            responseObserver: StreamObserver<BacktestResult>,
        ) {
            try {
                logger.atFine().log(
                    "Running backtest for strategy: %s with %d candles",
                    request.strategy.strategyName,
                    request.candlesCount,
                )

                val result = backtestRunner.runBacktest(request)

                logger.atFine().log(
                    "Backtest completed: strategy=%s, sharpe=%.4f, score=%.4f",
                    request.strategy.strategyName,
                    result.sharpeRatio,
                    result.strategyScore,
                )

                responseObserver.onNext(result)
                responseObserver.onCompleted()
            } catch (e: IllegalArgumentException) {
                logger.atWarning().withCause(e).log("Invalid backtest request")
                responseObserver.onError(
                    Status.INVALID_ARGUMENT
                        .withDescription(e.message)
                        .withCause(e)
                        .asRuntimeException(),
                )
            } catch (e: Exception) {
                logger.atSevere().withCause(e).log("Backtest failed unexpectedly")
                responseObserver.onError(
                    Status.INTERNAL
                        .withDescription("Backtest failed: ${e.message}")
                        .withCause(e)
                        .asRuntimeException(),
                )
            }
        }

        /**
         * Runs batch backtests for multiple parameter sets of the same strategy.
         * This is optimized for GA fitness evaluation where many parameter combinations
         * need to be tested against the same candle data.
         */
        override fun runBatchBacktest(
            request: BatchBacktestRequest,
            responseObserver: StreamObserver<BatchBacktestResult>,
        ) {
            try {
                logger.atFine().log(
                    "Running batch backtest: strategy=%s, batch_size=%d, candles=%d",
                    request.strategyName,
                    request.strategiesCount,
                    request.candlesCount,
                )

                // Execute backtests in parallel using the thread pool
                val futures =
                    request.strategiesList.map { strategy ->
                        batchExecutor.submit<BacktestResult> {
                            val singleRequest =
                                BacktestRequest
                                    .newBuilder()
                                    .addAllCandles(request.candlesList)
                                    .setStrategy(strategy)
                                    .build()
                            backtestRunner.runBacktest(singleRequest)
                        }
                    }

                // Collect results
                val results =
                    futures.map { future ->
                        try {
                            future.get(60, TimeUnit.SECONDS)
                        } catch (e: Exception) {
                            logger.atWarning().withCause(e).log("Single backtest in batch failed")
                            // Return a default result with negative infinity score for failed backtests
                            BacktestResult
                                .newBuilder()
                                .setStrategyScore(Double.NEGATIVE_INFINITY)
                                .build()
                        }
                    }

                val batchResult =
                    BatchBacktestResult
                        .newBuilder()
                        .addAllResults(results)
                        .build()

                logger.atFine().log(
                    "Batch backtest completed: %d results",
                    batchResult.resultsCount,
                )

                responseObserver.onNext(batchResult)
                responseObserver.onCompleted()
            } catch (e: Exception) {
                logger.atSevere().withCause(e).log("Batch backtest failed")
                responseObserver.onError(
                    Status.INTERNAL
                        .withDescription("Batch backtest failed: ${e.message}")
                        .withCause(e)
                        .asRuntimeException(),
                )
            }
        }

        /**
         * Runs walk-forward validation to detect overfitting.
         *
         * Walk-forward validation splits data into rolling train/test windows,
         * evaluates strategy performance on each, and aggregates results to
         * determine if the strategy generalizes to unseen data.
         */
        override fun runWalkForwardValidation(
            request: WalkForwardRequest,
            responseObserver: StreamObserver<WalkForwardResult>,
        ) {
            try {
                logger.atInfo().log(
                    "Running walk-forward validation: strategy=%s, candles=%d",
                    request.strategy.strategyName,
                    request.candlesCount,
                )

                // Run walk-forward validation
                val rawResult = walkForwardRunner.runWalkForwardValidation(request)

                // Skip validation if insufficient data
                val finalResult =
                    if (rawResult.status == ValidationStatus.INSUFFICIENT_DATA) {
                        rawResult
                    } else {
                        // Apply validation decision
                        strategyValidator.applyValidation(rawResult)
                    }

                logger.atInfo().log(
                    "Walk-forward validation completed: strategy=%s, status=%s, " +
                        "windows=%d, OOS_Sharpe=%.4f, degradation=%.1f%%",
                    request.strategy.strategyName,
                    finalResult.status,
                    finalResult.windowsCount,
                    finalResult.outOfSampleSharpe,
                    finalResult.sharpeDegradation * 100,
                )

                responseObserver.onNext(finalResult)
                responseObserver.onCompleted()
            } catch (e: IllegalArgumentException) {
                logger.atWarning().withCause(e).log("Invalid walk-forward request")
                responseObserver.onError(
                    Status.INVALID_ARGUMENT
                        .withDescription(e.message)
                        .withCause(e)
                        .asRuntimeException(),
                )
            } catch (e: Exception) {
                logger.atSevere().withCause(e).log("Walk-forward validation failed")
                responseObserver.onError(
                    Status.INTERNAL
                        .withDescription("Walk-forward validation failed: ${e.message}")
                        .withCause(e)
                        .asRuntimeException(),
                )
            }
        }

        /**
         * Shuts down the batch executor service.
         */
        fun shutdown() {
            logger.atInfo().log("Shutting down batch executor")
            batchExecutor.shutdown()
            try {
                if (!batchExecutor.awaitTermination(30, TimeUnit.SECONDS)) {
                    batchExecutor.shutdownNow()
                }
            } catch (e: InterruptedException) {
                batchExecutor.shutdownNow()
                Thread.currentThread().interrupt()
            }
        }
    }
