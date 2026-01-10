package com.verlumen.tradestream.backtesting

import com.verlumen.tradestream.marketdata.Candle

/**
 * Represents a single train/test split for walk-forward validation.
 *
 * @param trainCandles Candles for the training (in-sample) window
 * @param testCandles Candles for the test (out-of-sample) window
 * @param trainStartBar Start bar index of training window (relative to original series)
 * @param trainEndBar End bar index of training window (relative to original series)
 * @param testStartBar Start bar index of test window (relative to original series)
 * @param testEndBar End bar index of test window (relative to original series)
 */
data class TrainTestSplit(
    val trainCandles: List<Candle>,
    val testCandles: List<Candle>,
    val trainStartBar: Int,
    val trainEndBar: Int,
    val testStartBar: Int,
    val testEndBar: Int,
)

/**
 * Creates train/test splits for walk-forward optimization.
 *
 * Walk-forward optimization divides historical data into rolling windows:
 * - Train the strategy on the training window
 * - Evaluate on the test window (out-of-sample)
 * - Step forward and repeat
 *
 * This helps detect overfitting by ensuring strategies are validated on
 * data they've never seen during optimization.
 */
class WalkForwardSplitter {
    /**
     * Creates train/test splits from candle data based on the provided configuration.
     *
     * @param candles Full historical candle data
     * @param config Walk-forward configuration with window sizes
     * @return List of train/test splits, or empty if insufficient data
     */
    fun createSplits(
        candles: List<Candle>,
        config: WalkForwardConfig,
    ): List<TrainTestSplit> {
        val totalBars = candles.size
        val windowSize = config.trainWindowBars + config.testWindowBars

        // Check if we have enough data
        if (totalBars < windowSize) {
            return emptyList()
        }

        val splits = mutableListOf<TrainTestSplit>()
        var start = 0

        while (start + windowSize <= totalBars) {
            val trainStart = start
            val trainEnd = start + config.trainWindowBars
            val testStart = trainEnd
            val testEnd = trainEnd + config.testWindowBars

            splits.add(
                TrainTestSplit(
                    trainCandles = candles.subList(trainStart, trainEnd),
                    testCandles = candles.subList(testStart, testEnd),
                    trainStartBar = trainStart,
                    trainEndBar = trainEnd,
                    testStartBar = testStart,
                    testEndBar = testEnd,
                ),
            )

            start += config.stepBars
        }

        return splits
    }

    /**
     * Validates that the configuration and data are suitable for walk-forward validation.
     *
     * @param candles Full historical candle data
     * @param config Walk-forward configuration
     * @return Pair of (isValid, errorMessage)
     */
    fun validateConfig(
        candles: List<Candle>,
        config: WalkForwardConfig,
    ): Pair<Boolean, String?> {
        if (config.trainWindowBars <= 0) {
            return Pair(false, "Train window bars must be positive")
        }

        if (config.testWindowBars <= 0) {
            return Pair(false, "Test window bars must be positive")
        }

        if (config.stepBars <= 0) {
            return Pair(false, "Step bars must be positive")
        }

        if (config.minWindows <= 0) {
            return Pair(false, "Minimum windows must be positive")
        }

        val totalBars = candles.size
        val windowSize = config.trainWindowBars + config.testWindowBars

        if (totalBars < windowSize) {
            return Pair(
                false,
                "Insufficient data: need at least $windowSize bars, have $totalBars",
            )
        }

        // Count how many windows we can create
        var windowCount = 0
        var start = 0
        while (start + windowSize <= totalBars) {
            windowCount++
            start += config.stepBars
        }

        if (windowCount < config.minWindows) {
            return Pair(
                false,
                "Insufficient windows: need at least ${config.minWindows}, can create $windowCount",
            )
        }

        return Pair(true, null)
    }

    companion object {
        /**
         * Default configuration for walk-forward validation.
         *
         * Assumes 1-minute bars:
         * - Train: 6480 bars = ~9 months (1440 bars/day * 4.5 months assuming 24/7 trading)
         * - Test: 2160 bars = ~3 months
         * - Step: 2160 bars = 3 months (rolling quarterly)
         * - Min windows: 3
         */
        fun defaultConfig(): WalkForwardConfig =
            WalkForwardConfig
                .newBuilder()
                .setTrainWindowBars(6480)
                .setTestWindowBars(2160)
                .setStepBars(2160)
                .setMinWindows(3)
                .build()

        /**
         * Configuration for shorter timeframes or less data.
         *
         * - Train: 1000 bars
         * - Test: 250 bars
         * - Step: 250 bars
         * - Min windows: 3
         */
        fun shortConfig(): WalkForwardConfig =
            WalkForwardConfig
                .newBuilder()
                .setTrainWindowBars(1000)
                .setTestWindowBars(250)
                .setStepBars(250)
                .setMinWindows(3)
                .build()
    }
}
