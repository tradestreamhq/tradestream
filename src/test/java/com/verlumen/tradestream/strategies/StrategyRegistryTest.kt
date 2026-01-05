package com.verlumen.tradestream.strategies

import com.google.common.truth.Truth.assertThat
import com.verlumen.tradestream.strategies.configurable.StrategyConfig
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

/** Tests for StrategyRegistry. */
@RunWith(JUnit4::class)
class StrategyRegistryTest {
    @Test
    fun fromConfigs_createsRegistryWithStrategies() {
        val config1 = createTestConfig("STRATEGY_A")
        val config2 = createTestConfig("STRATEGY_B")

        val registry = StrategyRegistry.fromConfigs(listOf(config1, config2))

        assertThat(registry.size()).isEqualTo(2)
        assertThat(registry.isSupported("STRATEGY_A")).isTrue()
        assertThat(registry.isSupported("STRATEGY_B")).isTrue()
    }

    @Test
    fun getSpec_returnsCorrectSpec() {
        val config = createTestConfig("TEST_STRATEGY")
        val registry = StrategyRegistry.fromConfigs(listOf(config))

        val spec = registry.getSpec("TEST_STRATEGY")

        assertThat(spec).isNotNull()
        assertThat(spec.paramConfig).isNotNull()
        assertThat(spec.strategyFactory).isNotNull()
    }

    @Test(expected = NoSuchElementException::class)
    fun getSpec_throwsForUnknownStrategy() {
        val registry = StrategyRegistry.fromConfigs(listOf(createTestConfig("KNOWN")))

        registry.getSpec("UNKNOWN")
    }

    @Test
    fun getSpecOrNull_returnsNullForUnknownStrategy() {
        val registry = StrategyRegistry.fromConfigs(listOf(createTestConfig("KNOWN")))

        val spec = registry.getSpecOrNull("UNKNOWN")

        assertThat(spec).isNull()
    }

    @Test
    fun getSpecOrNull_returnsSpecForKnownStrategy() {
        val registry = StrategyRegistry.fromConfigs(listOf(createTestConfig("KNOWN")))

        val spec = registry.getSpecOrNull("KNOWN")

        assertThat(spec).isNotNull()
    }

    @Test
    fun isSupported_returnsTrueForRegisteredStrategy() {
        val registry = StrategyRegistry.fromConfigs(listOf(createTestConfig("MY_STRATEGY")))

        assertThat(registry.isSupported("MY_STRATEGY")).isTrue()
    }

    @Test
    fun isSupported_returnsFalseForUnregisteredStrategy() {
        val registry = StrategyRegistry.fromConfigs(listOf(createTestConfig("REGISTERED")))

        assertThat(registry.isSupported("NOT_REGISTERED")).isFalse()
    }

    @Test
    fun getSupportedStrategyNames_returnsSortedNames() {
        val config1 = createTestConfig("ZEBRA")
        val config2 = createTestConfig("ALPHA")
        val config3 = createTestConfig("BETA")

        val registry = StrategyRegistry.fromConfigs(listOf(config1, config2, config3))

        assertThat(registry.getSupportedStrategyNames())
            .containsExactly("ALPHA", "BETA", "ZEBRA")
            .inOrder()
    }

    @Test
    fun empty_createsEmptyRegistry() {
        val registry = StrategyRegistry.empty()

        assertThat(registry.size()).isEqualTo(0)
        assertThat(registry.getSupportedStrategyNames()).isEmpty()
    }

    @Test(expected = IllegalStateException::class)
    fun fromConfigs_throwsForEmptyList() {
        StrategyRegistry.fromConfigs(emptyList())
    }

    @Test(expected = IllegalStateException::class)
    fun fromConfigs_throwsForDuplicateNames() {
        val config1 = createTestConfig("DUPLICATE")
        val config2 = createTestConfig("DUPLICATE")

        StrategyRegistry.fromConfigs(listOf(config1, config2))
    }

    @Test
    fun getAllSpecs_returnsImmutableCopy() {
        val config = createTestConfig("TEST")
        val registry = StrategyRegistry.fromConfigs(listOf(config))

        val specs = registry.getAllSpecs()

        assertThat(specs).hasSize(1)
        assertThat(specs).containsKey("TEST")
    }

    /** Creates a minimal test StrategyConfig. */
    private fun createTestConfig(name: String): StrategyConfig =
        StrategyConfig
            .builder()
            .name(name)
            .description("Test strategy $name")
            .complexity("SIMPLE")
            .source("TEST")
            .indicators(emptyList())
            .entryConditions(emptyList())
            .exitConditions(emptyList())
            .parameters(emptyList())
            .build()
}
