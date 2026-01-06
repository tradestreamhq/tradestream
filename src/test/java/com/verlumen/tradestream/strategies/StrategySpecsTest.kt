package com.verlumen.tradestream.strategies

import com.google.common.truth.Truth.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class StrategySpecsTest {
    @Test
    fun `StrategySpecs getSpec returns spec for valid strategy name`() {
        // Act
        val spec = StrategySpecs.getSpec("MACD_CROSSOVER")

        // Assert
        assertThat(spec).isNotNull()
        assertThat(spec.strategyFactory).isNotNull()
    }

    @Test
    fun `StrategySpecs getSpec throws NoSuchElementException for invalid strategy name`() {
        // Act & Assert
        try {
            StrategySpecs.getSpec("INVALID_STRATEGY_NAME")
            throw AssertionError("Expected NoSuchElementException but none was thrown")
        } catch (exception: NoSuchElementException) {
            assertThat(exception.message).contains("Strategy not found: INVALID_STRATEGY_NAME")
        }
    }

    @Test
    fun `StrategySpecs getSpecOrNull returns spec for valid strategy name`() {
        // Act
        val spec = StrategySpecs.getSpecOrNull("SMA_EMA_CROSSOVER")

        // Assert
        assertThat(spec).isNotNull()
    }

    @Test
    fun `StrategySpecs getSpecOrNull returns null for invalid strategy name`() {
        // Act
        val spec = StrategySpecs.getSpecOrNull("INVALID_STRATEGY_NAME")

        // Assert
        assertThat(spec).isNull()
    }

    @Test
    fun `StrategySpecs isSupported returns true for valid strategy name`() {
        // Act & Assert
        assertThat(StrategySpecs.isSupported("MACD_CROSSOVER")).isTrue()
        assertThat(StrategySpecs.isSupported("RSI_EMA_CROSSOVER")).isTrue()
    }

    @Test
    fun `StrategySpecs isSupported returns false for invalid strategy name`() {
        // Act & Assert
        assertThat(StrategySpecs.isSupported("INVALID_STRATEGY")).isFalse()
        assertThat(StrategySpecs.isSupported("")).isFalse()
    }

    @Test
    fun `StrategySpecs getSupportedStrategyNames returns all strategy names`() {
        // Act
        val names = StrategySpecs.getSupportedStrategyNames()

        // Assert
        assertThat(names).hasSize(60)
        assertThat(names).contains("MACD_CROSSOVER")
        assertThat(names).contains("RSI_EMA_CROSSOVER")
        // Verify sorted
        assertThat(names).isEqualTo(names.sorted())
    }

    @Test
    fun `StrategySpecs size returns correct count`() {
        // Act & Assert
        assertThat(StrategySpecs.size()).isEqualTo(60)
    }

    @Test
    fun `all supported strategies have valid spec`() {
        // Act & Assert
        for (strategyName in StrategySpecs.getSupportedStrategyNames()) {
            val spec = StrategySpecs.getSpec(strategyName)
            assertThat(spec).isNotNull()
            assertThat(spec.strategyFactory).isNotNull()
            assertThat(spec.paramConfig).isNotNull()
        }
    }
}
