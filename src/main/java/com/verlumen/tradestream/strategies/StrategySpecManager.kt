package com.verlumen.tradestream.strategies

import com.google.inject.Inject

/**
 * Manages and provides StrategySpec instances for different strategy types.
 */
class StrategySpecManager @Inject constructor(
    private val specs: Map<StrategyType, StrategySpec>
) {
    fun getSpec(strategyType: StrategyType): StrategySpec {
        return specs[strategyType]
            ?: throw IllegalArgumentException("No spec found for strategy type: $strategyType")
    }

        fun getSupportedTypes(): Set<StrategyType> = specs.keys
    }
