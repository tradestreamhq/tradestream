package com.verlumen.tradestream.strategyspecs

import com.verlumen.tradestream.discovery.ParamConfig
import com.verlumen.tradestream.strategies.StrategyFactory

/**
 * A specification that encapsulates all components related to a trading strategy.
 *
 * @property paramConfig The configuration for the strategy's parameters, used for genetic optimization.
 * @property strategyFactory A factory for creating executable ta4j strategy instances.
 */
data class StrategySpec(
    val paramConfig: ParamConfig,
    val strategyFactory: StrategyFactory
)
