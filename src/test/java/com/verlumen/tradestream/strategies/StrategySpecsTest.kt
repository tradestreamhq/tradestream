package com.verlumen.tradestream.strategies

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.Any
import com.google.testing.junit.testparameterinjector.TestParameter
import com.google.testing.junit.testparameterinjector.TestParameterInjector
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeFalse
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.ta4j.core.BaseBarSeries

@RunWith(TestParameterInjector::class)
class StrategySpecsTest {
    private val barSeries = BaseBarSeries()

    @Test
    fun `strategy type has a spec defined`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Gracefully skip special, non-implementable enum values.
        // This prevents test failures for values we never intend to support.
        assumeFalse(
            "Skipping special enum value",
            strategyType == StrategyType.UNRECOGNIZED ||
                strategyType == StrategyType.UNSPECIFIED,
        )

        // The assertion that matters. This will fail for any valid strategy
        // that is missing from the `strategySpecMap`.
        assertTrue(
            "StrategySpec for '$strategyType' should be supported but was not. " +
                "Please add its entry to the 'strategySpecMap' in StrategySpecs.kt.",
            strategyType.isSupported(),
        )
    }

    @Test
    fun `createStrategy with default parameters returns strategy`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Skip if strategy not implemented yet
        assumeTrue("$strategyType strategy not implemented yet", strategyType.isSupported())

        // Act
        val result = strategyType.createStrategy(barSeries)

        // Assert
        assertThat(result).isNotNull()
    }

    @Test
    fun `createStrategy with custom parameters returns strategy`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Skip if strategy not implemented yet
        assumeTrue("$strategyType strategy not implemented yet", strategyType.isSupported())

        // Arrange - use default params as custom params for testing
        val defaultParams = strategyType.getDefaultParameters()

        // Act
        val result = strategyType.createStrategy(barSeries, defaultParams)

        // Assert
        assertThat(result).isNotNull()
    }

    @Test
    fun `getDefaultParameters returns packed default parameters`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Skip if strategy not implemented yet
        assumeTrue("$strategyType strategy not implemented yet", strategyType.isSupported())

        // Act
        val result = strategyType.getDefaultParameters()

        // Assert
        assertThat(result).isInstanceOf(Any::class.java)
        assertThat(result.typeUrl).isNotEmpty()
    }

    @Test
    fun `getStrategyFactory returns correct factory`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Skip if strategy not implemented yet
        assumeTrue("$strategyType strategy not implemented yet", strategyType.isSupported())

        // Act
        val result = strategyType.getStrategyFactory()

        // Assert
        assertThat(result).isNotNull()
        assertThat(result).isInstanceOf(StrategyFactory::class.java)
    }

    @Test
    fun `spec property returns correct spec for supported types`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Skip if strategy not implemented yet
        assumeTrue("$strategyType strategy not implemented yet", strategyType.isSupported())

        // Act
        val spec = strategyType.spec

        // Assert
        assertThat(spec).isNotNull()
        assertThat(spec.strategyFactory).isNotNull()
    }

    @Test
    fun `isSupported returns correct value for strategy type`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Act
        val isSupported = strategyType.isSupported()

        // Assert
        val supportedTypes = getSupportedStrategyTypes()
        if (strategyType in supportedTypes) {
            assertThat(isSupported).isTrue()
        } else {
            assertThat(isSupported).isFalse()
        }
    }

    @Test
    fun `unsupported strategy type throws NoSuchElementException for spec property`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Only test unsupported types
        assumeTrue("$strategyType is supported, skipping error test", !strategyType.isSupported())

        // Act & Assert
        try {
            strategyType.spec
            throw AssertionError("Expected NoSuchElementException but none was thrown")
        } catch (exception: NoSuchElementException) {
            assertThat(exception.message).contains("Strategy not found: $strategyType")
        }
    }

    @Test
    fun `unsupported strategy type throws NoSuchElementException for createStrategy`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Only test unsupported types
        assumeTrue("$strategyType is supported, skipping error test", !strategyType.isSupported())

        // Act & Assert
        try {
            strategyType.createStrategy(barSeries)
            throw AssertionError("Expected NoSuchElementException but none was thrown")
        } catch (exception: NoSuchElementException) {
            assertThat(exception.message).contains("Strategy not found: $strategyType")
        }
    }

    @Test
    fun `unsupported strategy type throws NoSuchElementException for getStrategyFactory`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Only test unsupported types
        assumeTrue("$strategyType is supported, skipping error test", !strategyType.isSupported())

        // Act & Assert
        try {
            strategyType.getStrategyFactory()
            throw AssertionError("Expected NoSuchElementException but none was thrown")
        } catch (exception: NoSuchElementException) {
            assertThat(exception.message).contains("Strategy not found: $strategyType")
        }
    }

    @Test
    fun `unsupported strategy type throws NoSuchElementException for getDefaultParameters`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Only test unsupported types
        assumeTrue("$strategyType is supported, skipping error test", !strategyType.isSupported())

        // Act & Assert
        try {
            strategyType.getDefaultParameters()
            throw AssertionError("Expected NoSuchElementException but none was thrown")
        } catch (exception: NoSuchElementException) {
            assertThat(exception.message).contains("Strategy not found: $strategyType")
        }
    }

    @Test
    fun `getSupportedStrategyTypes returns current implemented strategy types`() {
        // Act
        val result = getSupportedStrategyTypes()

        // Assert
        assertThat(result).isNotNull()
        assertThat(result).hasSize(60)
    }

    @Test
    fun `getSupportedStrategyTypes contains only strategy types that return true for isSupported`() {
        // Act
        val supportedTypes = getSupportedStrategyTypes()

        // Assert
        for (strategyType in supportedTypes) {
            assertThat(strategyType.isSupported()).isTrue()
        }

        // Verify the inverse - all supported types are in the list
        for (strategyType in StrategyType.values()) {
            if (strategyType.isSupported()) {
                assertThat(supportedTypes).contains(strategyType)
            }
        }
    }

    // Tests for the new string-based StrategySpecs API

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
    fun `StrategySpecs getSpec is consistent with StrategyType extension`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Only test supported types
        assumeTrue("$strategyType is not supported, skipping", strategyType.isSupported())

        // Act
        val specFromObject = StrategySpecs.getSpec(strategyType.name)

        @Suppress("DEPRECATION")
        val specFromExtension = strategyType.spec

        // Assert - both should return equivalent specs
        assertThat(specFromObject.strategyFactory.javaClass)
            .isEqualTo(specFromExtension.strategyFactory.javaClass)
    }
}
