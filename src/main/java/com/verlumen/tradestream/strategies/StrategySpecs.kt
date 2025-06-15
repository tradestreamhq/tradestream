package com.verlumen.tradestream.strategies

import com.verlumen.tradestream.strategies.emamacd.EmaMacdParamConfig
import com.verlumen.tradestream.strategies.emamacd.EmaMacdStrategyFactory
import com.verlumen.tradestream.strategies.smarsi.SmaRsiParamConfig
import com.verlumen.tradestream.strategies.smarsi.SmaRsiStrategyFactory

/**
 * The single source of truth for all implemented strategy specifications.
 * The map's keys define which strategies are considered "supported".
 */
private val strategySpecMap: Map<StrategyType, StrategySpec> = mapOf(
    StrategyType.SMA_RSI to StrategySpec(
        paramConfig = SmaRsiParamConfig.create(),
        strategyFactory = SmaRsiStrategyFactory.create()
    ),
    StrategyType.EMA_MACD to StrategySpec(
        paramConfig = EmaMacdParamConfig.create(),
        strategyFactory = EmaMacdStrategyFactory.create()
    )
    // To add a new strategy, just add a new entry here.
)

/**
 * An extension property that retrieves the corresponding [StrategySpec] from the central map.
 *
 * @throws NotImplementedError if no spec is defined for the given strategy type.
 */
val StrategyType.spec: StrategySpec
    get() = strategySpecMap[this]
        ?: throw NotImplementedError("No StrategySpec defined for strategy type: $this")

/**
 * An extension function that returns `true` if a [StrategySpec] has been
 * implemented for this [StrategyType] by checking for its key in the central map.
 */
fun StrategyType.isSupported(): Boolean {
    return strategySpecMap.containsKey(this)
}
