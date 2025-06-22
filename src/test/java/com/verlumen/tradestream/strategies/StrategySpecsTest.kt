package com.verlumen.tradestream.strategies

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.Any
import com.google.testing.junit.testparameterinjector.TestParameter
import com.google.testing.junit.testparameterinjector.TestParameterInjector
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.ta4j.core.BaseBarSeries

@RunWith(TestParameterInjector::class)
class StrategySpecsTest {
    private val barSeries = BaseBarSeries()

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
    fun `unsupported strategy type throws NotImplementedError for spec property`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Only test unsupported types
        assumeTrue("$strategyType is supported, skipping error test", !strategyType.isSupported())

        // Act & Assert
        try {
            strategyType.spec
            throw AssertionError("Expected NotImplementedError but none was thrown")
        } catch (exception: NotImplementedError) {
            assertThat(exception.message).contains("No StrategySpec defined for strategy type: $strategyType")
        }
    }

    @Test
    fun `unsupported strategy type throws NotImplementedError for createStrategy`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Only test unsupported types
        assumeTrue("$strategyType is supported, skipping error test", !strategyType.isSupported())

        // Act & Assert
        try {
            strategyType.createStrategy(barSeries)
            throw AssertionError("Expected NotImplementedError but none was thrown")
        } catch (exception: NotImplementedError) {
            assertThat(exception.message).contains("No StrategySpec defined for strategy type: $strategyType")
        }
    }

    @Test
    fun `unsupported strategy type throws NotImplementedError for getStrategyFactory`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Only test unsupported types
        assumeTrue("$strategyType is supported, skipping error test", !strategyType.isSupported())

        // Act & Assert
        try {
            strategyType.getStrategyFactory()
            throw AssertionError("Expected NotImplementedError but none was thrown")
        } catch (exception: NotImplementedError) {
            assertThat(exception.message).contains("No StrategySpec defined for strategy type: $strategyType")
        }
    }

    @Test
    fun `unsupported strategy type throws NotImplementedError for getDefaultParameters`(
        @TestParameter strategyType: StrategyType,
    ) {
        // Only test unsupported types
        assumeTrue("$strategyType is supported, skipping error test", !strategyType.isSupported())

        // Act & Assert
        try {
            strategyType.getDefaultParameters()
            throw AssertionError("Expected NotImplementedError but none was thrown")
        } catch (exception: NotImplementedError) {
            assertThat(exception.message).contains("No StrategySpec defined for strategy type: $strategyType")
        }
    }

    @Test
    fun `getSupportedStrategyTypes returns current implemented strategy types`() {
        // Act
        val result = getSupportedStrategyTypes()

        // Assert
        assertThat(result).isNotNull()
        assertThat(result).hasSize(21)
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
}
