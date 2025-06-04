package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.strategies.StrategyType
import java.io.Serializable

data class GAEngineParams(
    val strategyType: StrategyType,
    val candlesList: List<Candle>,
    val populationSize: Int,
) : Serializable {
    companion object {
        private const val serialVersionUID = 1L
    }
}
