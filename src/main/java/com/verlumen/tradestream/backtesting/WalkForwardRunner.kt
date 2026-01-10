package com.verlumen.tradestream.backtesting

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import kotlin.math.pow
import kotlin.math.sqrt

/**
 * Runs walk-forward validation on trading strategies.
 *
 * Walk-forward validation is the gold standard for detecting overfitting:
 * 1. Split data into rolling train/test windows
 * 2. Optimize strategy on training data
 * 3. Evaluate on test data (out-of-sample)
 * 4. Aggregate OOS performance across all windows
 *
 * A strategy that performs well in-sample but poorly out-of-sample is overfit.
 */
class WalkForwardRunner
    @Inject
    constructor(
        private val backtestRunner: BacktestRunner,
    ) {
        companion object {
            private val logger = FluentLogger.forEnclosingClass()
        }

        private val splitter = WalkForwardSplitter()

        /**
         * Runs walk-forward validation for the given strategy and candle data.
         *
         * @param request Walk-forward validation request
         * @return Walk-forward validation result with aggregated metrics
         */
        fun runWalkForwardValidation(request: WalkForwardRequest): WalkForwardResult {
            val config = request.config
            val candles = request.candlesList
            val strategy = request.strategy

            logger.atInfo().log(
                "Starting walk-forward validation for strategy: %s with %d candles",
                strategy.strategyName,
                candles.size,
            )

            // Validate configuration
            val (isValid, errorMessage) = splitter.validateConfig(candles, config)
            if (!isValid) {
                logger.atWarning().log("Invalid walk-forward config: %s", errorMessage)
                return WalkForwardResult
                    .newBuilder()
                    .setStatus(ValidationStatus.INSUFFICIENT_DATA)
                    .setRejectionReason(errorMessage ?: "Invalid configuration")
                    .build()
            }

            // Create train/test splits
            val splits = splitter.createSplits(candles, config)
            if (splits.size < config.minWindows) {
                logger.atWarning().log(
                    "Insufficient windows: got %d, need %d",
                    splits.size,
                    config.minWindows,
                )
                return WalkForwardResult
                    .newBuilder()
                    .setStatus(ValidationStatus.INSUFFICIENT_DATA)
                    .setRejectionReason(
                        "Insufficient windows: got ${splits.size}, need ${config.minWindows}",
                    ).build()
            }

            logger.atInfo().log("Created %d walk-forward windows", splits.size)

            // Run backtests on each window
            val windowResults = mutableListOf<WindowResult>()
            var windowIndex = 0

            for (split in splits) {
                logger.atFine().log(
                    "Running window %d: train[%d-%d], test[%d-%d]",
                    windowIndex,
                    split.trainStartBar,
                    split.trainEndBar,
                    split.testStartBar,
                    split.testEndBar,
                )

                // Run backtest on training data
                val trainRequest =
                    BacktestRequest
                        .newBuilder()
                        .setStrategy(strategy)
                        .addAllCandles(split.trainCandles)
                        .build()
                val trainResult = backtestRunner.runBacktest(trainRequest)

                // Run backtest on test data (out-of-sample)
                val testRequest =
                    BacktestRequest
                        .newBuilder()
                        .setStrategy(strategy)
                        .addAllCandles(split.testCandles)
                        .build()
                val testResult = backtestRunner.runBacktest(testRequest)

                windowResults.add(
                    WindowResult
                        .newBuilder()
                        .setWindowIndex(windowIndex)
                        .setInSampleResult(trainResult)
                        .setOutOfSampleResult(testResult)
                        .setTrainStartBar(split.trainStartBar)
                        .setTrainEndBar(split.trainEndBar)
                        .setTestStartBar(split.testStartBar)
                        .setTestEndBar(split.testEndBar)
                        .build(),
                )

                logger.atFine().log(
                    "Window %d: IS Sharpe=%.4f, OOS Sharpe=%.4f",
                    windowIndex,
                    trainResult.sharpeRatio,
                    testResult.sharpeRatio,
                )

                windowIndex++
            }

            // Aggregate metrics
            return aggregateResults(windowResults)
        }

        /**
         * Aggregates results from all walk-forward windows into a single result.
         */
        private fun aggregateResults(windowResults: List<WindowResult>): WalkForwardResult {
            if (windowResults.isEmpty()) {
                return WalkForwardResult
                    .newBuilder()
                    .setStatus(ValidationStatus.INSUFFICIENT_DATA)
                    .setRejectionReason("No window results to aggregate")
                    .build()
            }

            // Calculate mean in-sample metrics
            val inSampleSharpes = windowResults.map { it.inSampleResult.sharpeRatio }
            val outOfSampleSharpes = windowResults.map { it.outOfSampleResult.sharpeRatio }
            val inSampleReturns = windowResults.map { it.inSampleResult.cumulativeReturn }
            val outOfSampleReturns = windowResults.map { it.outOfSampleResult.cumulativeReturn }

            val meanInSampleSharpe = inSampleSharpes.average()
            val meanOutOfSampleSharpe = outOfSampleSharpes.average()
            val meanInSampleReturn = inSampleReturns.average()
            val meanOutOfSampleReturn = outOfSampleReturns.average()

            // Calculate Sharpe degradation
            val sharpeDegradation =
                if (meanInSampleSharpe != 0.0) {
                    1.0 - (meanOutOfSampleSharpe / meanInSampleSharpe)
                } else {
                    0.0
                }

            // Calculate return degradation
            val returnDegradation =
                if (meanInSampleReturn != 0.0) {
                    1.0 - (meanOutOfSampleReturn / meanInSampleReturn)
                } else {
                    0.0
                }

            // Calculate OOS Sharpe standard deviation (consistency metric)
            val oosSharpeMean = outOfSampleSharpes.average()
            val oosSharpeVariance =
                outOfSampleSharpes.map { (it - oosSharpeMean).pow(2) }.average()
            val oosSharpeStdDev = sqrt(oosSharpeVariance)

            logger.atInfo().log(
                "Walk-forward results: IS Sharpe=%.4f, OOS Sharpe=%.4f, " +
                    "Degradation=%.2f%%, OOS StdDev=%.4f",
                meanInSampleSharpe,
                meanOutOfSampleSharpe,
                sharpeDegradation * 100,
                oosSharpeStdDev,
            )

            return WalkForwardResult
                .newBuilder()
                .setStatus(ValidationStatus.PENDING) // Will be determined by StrategyValidator
                .setWindowsCount(windowResults.size)
                .setInSampleSharpe(meanInSampleSharpe)
                .setOutOfSampleSharpe(meanOutOfSampleSharpe)
                .setSharpeDegradation(sharpeDegradation)
                .setOosSharpeStdDev(oosSharpeStdDev)
                .setInSampleReturn(meanInSampleReturn)
                .setOutOfSampleReturn(meanOutOfSampleReturn)
                .setReturnDegradation(returnDegradation)
                .addAllWindowResults(windowResults)
                .build()
        }
    }
