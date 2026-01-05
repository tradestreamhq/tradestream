package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.strategies.StrategyType
import java.io.Serializable

data class GAEngineParams(
    val strategyName: String,
    val candlesList: List<Candle>,
    val populationSize: Int,
) : Serializable {
    companion object {
        private const val serialVersionUID = 1L
    }

    /**
     * Gets the strategy type from the strategy name.
     * @deprecated Use [strategyName] directly instead
     */
    @Deprecated("Use strategyName directly")
    val strategyType: StrategyType
        get() = StrategyType.valueOf(strategyName)
}
