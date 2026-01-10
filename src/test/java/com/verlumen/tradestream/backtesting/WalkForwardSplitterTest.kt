package com.verlumen.tradestream.backtesting

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.Timestamp
import com.verlumen.tradestream.marketdata.Candle
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class WalkForwardSplitterTest {
    private lateinit var splitter: WalkForwardSplitter

    @Before
    fun setUp() {
        splitter = WalkForwardSplitter()
    }

    @Test
    fun createSplits_withSufficientData_returnsCorrectNumberOfWindows() {
        // Arrange: 20 candles with config requiring 6 train + 2 test per window, step 2
        val candles = createCandles(20)
        val config =
            WalkForwardConfig
                .newBuilder()
                .setTrainWindowBars(6)
                .setTestWindowBars(2)
                .setStepBars(2)
                .setMinWindows(2)
                .build()

        // Act
        val splits = splitter.createSplits(candles, config)

        // Assert: Should create 7 windows (at positions 0, 2, 4, 6, 8, 10, 12)
        // Position 14+ would need 8 bars but only have 6 remaining
        assertThat(splits).hasSize(7)
    }

    @Test
    fun createSplits_withInsufficientData_returnsEmptyList() {
        // Arrange: Only 5 candles but need 6 + 2 = 8
        val candles = createCandles(5)
        val config =
            WalkForwardConfig
                .newBuilder()
                .setTrainWindowBars(6)
                .setTestWindowBars(2)
                .setStepBars(2)
                .setMinWindows(1)
                .build()

        // Act
        val splits = splitter.createSplits(candles, config)

        // Assert
        assertThat(splits).isEmpty()
    }

    @Test
    fun createSplits_withExactData_returnsOneWindow() {
        // Arrange: Exactly 8 candles for one window
        val candles = createCandles(8)
        val config =
            WalkForwardConfig
                .newBuilder()
                .setTrainWindowBars(6)
                .setTestWindowBars(2)
                .setStepBars(2)
                .setMinWindows(1)
                .build()

        // Act
        val splits = splitter.createSplits(candles, config)

        // Assert
        assertThat(splits).hasSize(1)
        assertThat(splits[0].trainCandles).hasSize(6)
        assertThat(splits[0].testCandles).hasSize(2)
    }

    @Test
    fun createSplits_verifyWindowBoundaries() {
        // Arrange
        val candles = createCandles(15)
        val config =
            WalkForwardConfig
                .newBuilder()
                .setTrainWindowBars(5)
                .setTestWindowBars(3)
                .setStepBars(4)
                .setMinWindows(1)
                .build()

        // Act
        val splits = splitter.createSplits(candles, config)

        // Assert: First window
        assertThat(splits[0].trainStartBar).isEqualTo(0)
        assertThat(splits[0].trainEndBar).isEqualTo(5)
        assertThat(splits[0].testStartBar).isEqualTo(5)
        assertThat(splits[0].testEndBar).isEqualTo(8)

        // Assert: Second window (stepped by 4)
        assertThat(splits[1].trainStartBar).isEqualTo(4)
        assertThat(splits[1].trainEndBar).isEqualTo(9)
        assertThat(splits[1].testStartBar).isEqualTo(9)
        assertThat(splits[1].testEndBar).isEqualTo(12)
    }

    @Test
    fun validateConfig_withValidConfig_returnsTrue() {
        // Arrange
        val candles = createCandles(100)
        val config =
            WalkForwardConfig
                .newBuilder()
                .setTrainWindowBars(30)
                .setTestWindowBars(10)
                .setStepBars(10)
                .setMinWindows(3)
                .build()

        // Act
        val (isValid, errorMessage) = splitter.validateConfig(candles, config)

        // Assert
        assertThat(isValid).isTrue()
        assertThat(errorMessage).isNull()
    }

    @Test
    fun validateConfig_withZeroTrainWindow_returnsFalse() {
        // Arrange
        val candles = createCandles(100)
        val config =
            WalkForwardConfig
                .newBuilder()
                .setTrainWindowBars(0)
                .setTestWindowBars(10)
                .setStepBars(10)
                .setMinWindows(3)
                .build()

        // Act
        val (isValid, errorMessage) = splitter.validateConfig(candles, config)

        // Assert
        assertThat(isValid).isFalse()
        assertThat(errorMessage).contains("Train window bars must be positive")
    }

    @Test
    fun validateConfig_withInsufficientWindows_returnsFalse() {
        // Arrange: Config requires 5 windows but data only allows 2
        val candles = createCandles(30)
        val config =
            WalkForwardConfig
                .newBuilder()
                .setTrainWindowBars(10)
                .setTestWindowBars(5)
                .setStepBars(10)
                .setMinWindows(5)
                .build()

        // Act
        val (isValid, errorMessage) = splitter.validateConfig(candles, config)

        // Assert
        assertThat(isValid).isFalse()
        assertThat(errorMessage).contains("Insufficient windows")
    }

    @Test
    fun defaultConfig_hasReasonableDefaults() {
        // Act
        val config = WalkForwardSplitter.defaultConfig()

        // Assert
        assertThat(config.trainWindowBars).isEqualTo(6480)
        assertThat(config.testWindowBars).isEqualTo(2160)
        assertThat(config.stepBars).isEqualTo(2160)
        assertThat(config.minWindows).isEqualTo(3)
    }

    @Test
    fun shortConfig_hasSmallerWindows() {
        // Act
        val config = WalkForwardSplitter.shortConfig()

        // Assert
        assertThat(config.trainWindowBars).isEqualTo(1000)
        assertThat(config.testWindowBars).isEqualTo(250)
        assertThat(config.stepBars).isEqualTo(250)
        assertThat(config.minWindows).isEqualTo(3)
    }

    private fun createCandles(count: Int): List<Candle> {
        val baseTime = 1700000000L // Some fixed timestamp
        return (0 until count).map { i ->
            Candle
                .newBuilder()
                .setTimestamp(
                    Timestamp
                        .newBuilder()
                        .setSeconds(baseTime + i * 60)
                        .build(),
                ).setCurrencyPair("BTC/USD")
                .setOpen(50000.0 + i * 10)
                .setHigh(50100.0 + i * 10)
                .setLow(49900.0 + i * 10)
                .setClose(50050.0 + i * 10)
                .setVolume(10.0)
                .build()
        }
    }
}
